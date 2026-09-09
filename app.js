// =====================
// PASSWORD PROTECTION (Server-side)
// =====================
// Password is validated on the server using environment variable
// Set APP_PASSWORD in Vercel Dashboard > Settings > Environment Variables

function checkAuth() {
  const token = sessionStorage.getItem('ss_auth_token');
  return token && token.length > 0;
}

function showApp() {
  document.getElementById('loginOverlay').style.display = 'none';
  document.getElementById('appShell').style.display = 'flex';
}

function showLogin() {
  document.getElementById('loginOverlay').style.display = 'flex';
  document.getElementById('appShell').style.display = 'none';
}

async function handleLogin(e) {
  e.preventDefault();
  const password = document.getElementById('passwordInput').value;
  const errorEl = document.getElementById('loginError');
  const loginBtn = document.querySelector('.login-button');

  loginBtn.disabled = true;
  loginBtn.textContent = 'Verifying...';
  errorEl.textContent = '';

  try {
    const response = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });

    const result = await response.json();

    if (result.success && result.token) {
      sessionStorage.setItem('ss_auth_token', result.token);
      showApp();
    } else {
      errorEl.textContent = result.error || 'Incorrect password. Please try again.';
      document.getElementById('passwordInput').value = '';
    }
  } catch (error) {
    console.error('Auth error:', error);
    errorEl.textContent = 'Connection error. Please try again.';
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'Login';
  }
}

function handleLogout() {
  sessionStorage.removeItem('ss_auth_token');
  currentRankingData = [];
  showLogin();
}

// Initialize auth check
document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('loginForm');
  const logoutBtn = document.getElementById('logoutBtn');

  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }

  if (logoutBtn) {
    logoutBtn.addEventListener('click', handleLogout);
  }

  // Check if already authenticated
  if (checkAuth()) {
    showApp();
  } else {
    showLogin();
  }
});

// =====================
// MAIN APP CODE
// =====================

const sampleJobDescription = `Senior Data Analyst with strong business communication, SQL, Python, dashboard design, stakeholder management, and experience translating source data into measurable insights for executive decision-making.`;

// Store current ranking data for export
let currentRankingData = [];

// =====================
// INDEXEDDB STORAGE
// =====================
const DB_NAME = 'SmartScreenerDB';
const DB_VERSION = 1;
const STORE_NAME = 'resumes';
let db = null;

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const database = event.target.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        store.createIndex('name', 'name', { unique: false });
        store.createIndex('savedAt', 'savedAt', { unique: false });
      }
    };
  });
}

function saveResumeToLibrary(resume) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.add({
      ...resume,
      savedAt: new Date().toISOString()
    });

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function getAllResumes() {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.getAll();

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function getResumeById(id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.get(id);

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function deleteResumeById(id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.delete(id);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function deleteMultipleResumes(ids) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    let completed = 0;
    ids.forEach(id => {
      const request = store.delete(id);
      request.onsuccess = () => {
        completed++;
        if (completed === ids.length) resolve();
      };
      request.onerror = () => reject(request.error);
    });

    if (ids.length === 0) resolve();
  });
}

const jobDescription = document.getElementById('jobDescription');
const scanButton = document.getElementById('scanButton');
const loadJobButton = document.getElementById('loadJobButton');
const resumeFiles = document.getElementById('resumeFiles');
const dropZone = document.getElementById('dropZone');
const fileList = document.getElementById('fileList');
const uploadStatus = document.getElementById('uploadStatus');
const rankingList = document.getElementById('rankingList');
const resultsTable = document.getElementById('resultsTable');
const clearFiles = document.getElementById('clearFiles');
const bestCandidateCard = document.getElementById('bestCandidateCard');
const exportCsvBtn = document.getElementById('exportCsvBtn');
const exportExcelBtn = document.getElementById('exportExcelBtn');
const refreshBtn = document.getElementById('refreshBtn');

function getInitials(name) {
  if (!name) return '??';
  return name.split(' ').map(n => n.slice(0, 1)).slice(0, 2).join('').toUpperCase();
}

function capitalize(value) {
  if (!value) return '';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

// Extract contact info from resume text
function extractContactInfo(text) {
  const emailMatch = text.match(/[\w.-]+@[\w.-]+\.\w+/);
  const phoneMatch = text.match(/(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/);
  const linkedinMatch = text.match(/linkedin\.com\/in\/[\w-]+/i);

  return {
    email: emailMatch ? emailMatch[0] : '',
    phone: phoneMatch ? phoneMatch[0] : '',
    linkedin: linkedinMatch ? 'https://' + linkedinMatch[0] : ''
  };
}

// Extract location from resume text
function extractLocation(text) {
  const locationPatterns = [
    /(?:Location|Address|City):\s*([^\n,]+(?:,\s*[^\n]+)?)/i,
    /([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*(?:CA|NY|TX|FL|WA|IL|PA|OH|GA|NC|MI|NJ|VA|AZ|MA|TN|IN|MO|MD|WI|CO|MN|SC|AL|LA|KY|OR|OK|CT|UT|IA|NV|AR|MS|KS|NM|NE|WV|ID|HI|NH|ME|MT|RI|DE|SD|ND|AK|VT|WY|DC))/,
    /(Remote|Hybrid|On-site)/i
  ];

  for (const pattern of locationPatterns) {
    const match = text.match(pattern);
    if (match) return match[1] || match[0];
  }
  return '';
}

// Extract experience info
function extractExperience(text) {
  const expMatch = text.match(/(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)?/i);
  return expMatch ? parseInt(expMatch[1]) : 0;
}

// Extract current role and company
function extractCurrentRole(text) {
  const lines = text.split('\n');
  let currentRole = '';
  let currentCompany = '';

  for (let i = 0; i < Math.min(lines.length, 20); i++) {
    const line = lines[i].trim();
    if (line.match(/^(Senior|Junior|Lead|Principal|Staff|Chief|Head|Director|Manager|Engineer|Developer|Analyst|Specialist|Consultant)/i)) {
      currentRole = line.split(/\s*[|@-]\s*/)[0].trim();
      const companyMatch = line.match(/(?:at|@|-)\s*(.+)/i);
      if (companyMatch) currentCompany = companyMatch[1].trim();
      break;
    }
  }

  return { currentRole, currentCompany };
}

// Extract education
function extractEducation(text) {
  const eduPatterns = [
    /(Bachelor|Master|PhD|Ph\.D|MBA|B\.S\.|M\.S\.|B\.A\.|M\.A\.|B\.Tech|M\.Tech|B\.E\.|M\.E\.)[^.\n]*/i,
    /(Computer Science|Engineering|Business|Mathematics|Statistics|Data Science|Information Technology)/i
  ];

  for (const pattern of eduPatterns) {
    const match = text.match(pattern);
    if (match) return match[0].trim();
  }
  return '';
}

function renderRankings(ranking) {
  if (!ranking || ranking.length === 0) {
    rankingList.innerHTML = '<div class="empty-state">No candidates to display</div>';
    return;
  }

  const sorted = [...ranking].sort((a, b) => b.score - a.score);
  rankingList.innerHTML = '';

  sorted.slice(0, 5).forEach((item, index) => {
    const row = document.createElement('div');
    row.className = 'rank-row';
    const barWidth = Math.min(100, Math.max(30, item.score));
    const barClass = index === 0 ? 'rank-high' : item.score >= 75 ? 'rank-mid' : 'rank-low';

    row.innerHTML = `
      <span class="rank-name">${item.name || 'Unknown'}</span>
      <span class="rank-bar-wrap"><span class="rank-bar ${barClass}" style="width:${barWidth}%;"></span></span>
      <span class="rank-score">${item.score || 0}</span>
    `;
    rankingList.appendChild(row);
  });
}

function renderResultsTable(ranking) {
  if (!ranking || ranking.length === 0) {
    resultsTable.innerHTML = '<tr><td colspan="10" class="empty-state">No candidates to display</td></tr>';
    return;
  }

  const sorted = [...ranking].sort((a, b) => b.score - a.score);
  resultsTable.innerHTML = '';

  sorted.forEach((item, index) => {
    const tr = document.createElement('tr');
    const decision = item.score >= 85 ? 'Shortlist' : item.score >= 70 ? 'Review' : 'Pool';
    const decisionClass = item.score >= 85 ? 'decision-shortlist' : item.score >= 70 ? 'decision-review' : 'decision-pool';
    const skills = Array.isArray(item.skills) ? item.skills.slice(0, 3).join(', ') :
                   (item.coveredSkills ? item.coveredSkills.slice(0, 3).join(', ') : '');

    tr.innerHTML = `
      <td class="rank-token">${String(index + 1).padStart(2, '0')}</td>
      <td><span class="table-name">${item.name || 'Unknown'}</span></td>
      <td>${item.email || '-'}</td>
      <td>${item.phone || '-'}</td>
      <td>${item.location || '-'}</td>
      <td>${item.experience || 0} yrs</td>
      <td>${item.currentRole || item.title || '-'}</td>
      <td>${skills || '-'}</td>
      <td><span class="score-number">${item.score || 0}</span></td>
      <td><span class="decision ${decisionClass}">${decision}</span></td>
    `;
    resultsTable.appendChild(tr);
  });
}

function renderBestCandidate(ranking) {
  if (!ranking || ranking.length === 0) {
    bestCandidateCard.innerHTML = '<div class="empty-state">No candidates analyzed yet</div>';
    return;
  }

  const sorted = [...ranking].sort((a, b) => b.score - a.score);
  const top = sorted[0];
  const skills = Array.isArray(top.skills) ? top.skills.slice(0, 4).join(', ') :
                 (top.coveredSkills ? top.coveredSkills.map(capitalize).join(', ') : 'N/A');

  bestCandidateCard.innerHTML = `
    <div class="candidate-head">
      <div>
        <span class="candidate-avatar">${getInitials(top.name)}</span>
      </div>
      <div>
        <span class="candidate-name">${top.name || 'Unknown'}</span>
        <span class="candidate-title">${top.currentRole || top.title || 'Candidate'}</span>
      </div>
      <span class="candidate-score">${top.score || 0}</span>
    </div>
    <div class="candidate-body">
      <div class="candidate-details">
        <div>
          <span class="candidate-label">Experience</span>
          <span class="candidate-value">${top.experience || 0} years</span>
        </div>
        <div>
          <span class="candidate-label">Skills</span>
          <span class="candidate-value">${skills}</span>
        </div>
      </div>
      <div class="candidate-readiness">
        <span class="readiness-title">Contact</span>
        <span class="readiness-text">${top.email || 'No email available'}</span>
      </div>
    </div>
  `;
}

function updateDashboardMetrics(ranking) {
  if (!ranking || ranking.length === 0) {
    document.getElementById('metricScanned').textContent = '00';
    document.getElementById('metricTopScore').textContent = '--';
    document.getElementById('metricCoverage').textContent = '--';
    document.getElementById('metricShortlist').textContent = '00';
    document.getElementById('pipelineBar').style.width = '0%';
    document.getElementById('pipelineScore').textContent = '0%';
    return;
  }

  const sorted = [...ranking].sort((a, b) => b.score - a.score);
  const top = sorted[0];
  const total = ranking.length;
  const shortlisted = ranking.filter(item => item.score >= 85).length;
  const avgScore = Math.round(ranking.reduce((sum, r) => sum + (r.score || 0), 0) / total);

  document.getElementById('metricScanned').textContent = String(total).padStart(2, '0');
  document.getElementById('metricTopScore').textContent = String(top.score || 0);
  document.getElementById('metricCoverage').textContent = avgScore + '%';
  document.getElementById('metricShortlist').textContent = String(shortlisted).padStart(2, '0');
  document.getElementById('pipelineBar').style.width = avgScore + '%';
  document.getElementById('pipelineScore').textContent = avgScore + '%';
}

function refreshFileList(files) {
  fileList.innerHTML = '';

  if (files.length === 0) {
    fileList.innerHTML = '<div class="empty-files">No resumes selected</div>';
    uploadStatus.textContent = '0 files';
    return;
  }

  files.forEach(file => {
    const row = document.createElement('div');
    row.className = 'file-item';
    row.innerHTML = `
      <span class="file-name">${file.name}</span>
      <span class="file-meta">${Math.round(file.size / 1024)} KB</span>
    `;
    fileList.appendChild(row);
  });

  uploadStatus.textContent = `${files.length} file${files.length > 1 ? 's' : ''}`;
}

async function runAnalysis() {
  const jobText = jobDescription.value;

  if (!jobText.trim()) {
    alert('Please enter a job description first.');
    return;
  }

  const uploadFiles = Array.from(resumeFiles.files);

  if (uploadFiles.length === 0) {
    alert('Please upload at least one resume.');
    return;
  }

  scanButton.disabled = true;
  scanButton.innerHTML = '<span>Scanning...</span>';

  const uploadedResumes = [];

  try {
    for (const file of uploadFiles) {
      const text = await file.text();
      const contactInfo = extractContactInfo(text);
      const roleInfo = extractCurrentRole(text);

      uploadedResumes.push({
        name: file.name.replace(/\.[^/.]+$/, '').split(/[_-]/).map(capitalize).join(' '),
        resume: text,
        email: contactInfo.email,
        phone: contactInfo.phone,
        linkedin: contactInfo.linkedin,
        location: extractLocation(text),
        experience: extractExperience(text),
        currentRole: roleInfo.currentRole,
        currentCompany: roleInfo.currentCompany,
        education: extractEducation(text)
      });
    }
  } catch (error) {
    console.warn('Error reading files:', error);
  }

  const payload = {
    jobDescription: jobText,
    resumes: uploadedResumes
  };

  try {
    const response = await fetch('/api/rank', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    const result = await response.json();
    let ranking = Array.isArray(result.ranking) ? result.ranking : [];

    // Merge extracted info with API results
    ranking = ranking.map((r, i) => {
      const uploaded = uploadedResumes.find(u => u.name === r.name) || uploadedResumes[i] || {};
      return {
        ...r,
        email: r.email || uploaded.email || '',
        phone: r.phone || uploaded.phone || '',
        linkedin: r.linkedin || uploaded.linkedin || '',
        location: r.location || uploaded.location || '',
        currentRole: r.currentRole || uploaded.currentRole || r.title || '',
        currentCompany: r.currentCompany || uploaded.currentCompany || '',
        education: r.education || uploaded.education || '',
        experience: r.experience || uploaded.experience || 0
      };
    });

    currentRankingData = ranking;
    renderRankings(ranking);
    renderResultsTable(ranking);
    renderBestCandidate(ranking);
    updateDashboardMetrics(ranking);

  } catch (error) {
    console.error('Analysis error:', error);
    alert('Error analyzing resumes. Please try again.');
  } finally {
    scanButton.disabled = false;
    scanButton.innerHTML = '<span>Scan Resumes</span>';
  }
}

// Export to CSV
function exportToCSV() {
  if (currentRankingData.length === 0) {
    alert('No data to export. Please scan resumes first.');
    return;
  }

  const headers = [
    'Name', 'Email', 'Phone', 'Location', 'Total Experience',
    'Current Role', 'Current Company', 'Skills', 'Education',
    'LinkedIn', 'AI Resume Score'
  ];

  const rows = currentRankingData.map(r => [
    r.name || '',
    r.email || '',
    r.phone || '',
    r.location || '',
    r.experience || 0,
    r.currentRole || r.title || '',
    r.currentCompany || '',
    Array.isArray(r.skills) ? r.skills.join('; ') : (r.coveredSkills ? r.coveredSkills.join('; ') : ''),
    r.education || '',
    r.linkedin || '',
    r.score || 0
  ]);

  const csvContent = [headers, ...rows]
    .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  downloadFile(csvContent, 'resume-report.csv', 'text/csv');
}

// Export to Excel (CSV format that Excel opens)
function exportToExcel() {
  if (currentRankingData.length === 0) {
    alert('No data to export. Please scan resumes first.');
    return;
  }

  const headers = [
    'Name', 'Email', 'Phone', 'Location', 'Total Experience',
    'Current Role', 'Current Company', 'Skills', 'Education',
    'LinkedIn', 'AI Resume Score'
  ];

  const rows = currentRankingData.map(r => [
    r.name || '',
    r.email || '',
    r.phone || '',
    r.location || '',
    r.experience || 0,
    r.currentRole || r.title || '',
    r.currentCompany || '',
    Array.isArray(r.skills) ? r.skills.join('; ') : (r.coveredSkills ? r.coveredSkills.join('; ') : ''),
    r.education || '',
    r.linkedin || '',
    r.score || 0
  ]);

  // Tab-separated for better Excel compatibility
  const content = [headers, ...rows]
    .map(row => row.map(cell => String(cell).replace(/\t/g, ' ')).join('\t'))
    .join('\n');

  downloadFile(content, 'resume-report.xls', 'application/vnd.ms-excel');
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType + ';charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

// Event Listeners
scanButton.addEventListener('click', runAnalysis);

loadJobButton.addEventListener('click', () => {
  jobDescription.value = sampleJobDescription;
});

clearFiles.addEventListener('click', () => {
  resumeFiles.value = '';
  refreshFileList([]);
  currentRankingData = [];
  renderRankings([]);
  renderResultsTable([]);
  renderBestCandidate([]);
  updateDashboardMetrics([]);
});

resumeFiles.addEventListener('change', event => {
  refreshFileList(Array.from(event.target.files));
});

exportCsvBtn.addEventListener('click', exportToCSV);
exportExcelBtn.addEventListener('click', exportToExcel);

refreshBtn.addEventListener('click', () => {
  if (currentRankingData.length > 0) {
    runAnalysis();
  }
});

// Drag and drop
dropZone.addEventListener('click', () => resumeFiles.click());

dropZone.addEventListener('dragover', event => {
  event.preventDefault();
  dropZone.style.borderColor = '#246b68';
});

dropZone.addEventListener('dragleave', () => {
  dropZone.style.borderColor = '#dae7e8';
});

dropZone.addEventListener('drop', event => {
  event.preventDefault();
  dropZone.style.borderColor = '#dae7e8';
  resumeFiles.files = event.dataTransfer.files;
  refreshFileList(Array.from(event.dataTransfer.files));
});

// =====================
// LIBRARY FUNCTIONALITY
// =====================
const libraryGrid = document.getElementById('libraryGrid');
const libraryCount = document.getElementById('libraryCount');
const saveResumesBtn = document.getElementById('saveResumesBtn');
const selectAllBtn = document.getElementById('selectAllBtn');
const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
const resumeModal = document.getElementById('resumeModal');
const modalTitle = document.getElementById('modalTitle');
const resumeContent = document.getElementById('resumeContent');
const closeModal = document.getElementById('closeModal');

let selectedResumeIds = new Set();

function updateLibraryCount(count) {
  if (libraryCount) {
    libraryCount.textContent = count;
  }
}

function formatDate(isoString) {
  const date = new Date(isoString);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

async function renderLibrary() {
  try {
    const resumes = await getAllResumes();
    updateLibraryCount(resumes.length);
    selectedResumeIds.clear();

    if (resumes.length === 0) {
      libraryGrid.innerHTML = '<div class="empty-state">No resumes in library. Upload and save resumes to build your library.</div>';
      return;
    }

    libraryGrid.innerHTML = '';
    resumes.sort((a, b) => new Date(b.savedAt) - new Date(a.savedAt));

    resumes.forEach(resume => {
      const item = document.createElement('div');
      item.className = 'library-item';
      item.dataset.id = resume.id;

      item.innerHTML = `
        <div class="library-item-header">
          <input type="checkbox" class="library-item-checkbox" data-id="${resume.id}" />
          <span class="library-item-name">${resume.name || 'Unknown'}</span>
        </div>
        <div class="library-item-meta">
          Saved: ${formatDate(resume.savedAt)}
        </div>
        <div class="library-item-actions">
          <button class="library-item-btn view-btn" data-id="${resume.id}">View</button>
          <button class="library-item-btn danger delete-btn" data-id="${resume.id}">Delete</button>
        </div>
      `;

      libraryGrid.appendChild(item);
    });

    // Add event listeners
    document.querySelectorAll('.library-item-checkbox').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        const id = parseInt(e.target.dataset.id);
        const item = e.target.closest('.library-item');
        if (e.target.checked) {
          selectedResumeIds.add(id);
          item.classList.add('selected');
        } else {
          selectedResumeIds.delete(id);
          item.classList.remove('selected');
        }
      });
    });

    document.querySelectorAll('.view-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = parseInt(e.target.dataset.id);
        await viewResume(id);
      });
    });

    document.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = parseInt(e.target.dataset.id);
        if (confirm('Are you sure you want to delete this resume?')) {
          await deleteResumeById(id);
          await renderLibrary();
        }
      });
    });

  } catch (error) {
    console.error('Error rendering library:', error);
    libraryGrid.innerHTML = '<div class="empty-state">Error loading library.</div>';
  }
}

async function viewResume(id) {
  try {
    const resume = await getResumeById(id);
    if (resume) {
      modalTitle.textContent = resume.name || 'Resume';
      resumeContent.textContent = resume.content || resume.resume || 'No content available';
      resumeModal.style.display = 'flex';
    }
  } catch (error) {
    console.error('Error viewing resume:', error);
    alert('Error loading resume.');
  }
}

function closeResumeModal() {
  resumeModal.style.display = 'none';
}

async function saveUploadedResumes() {
  const uploadFiles = Array.from(resumeFiles.files);

  if (uploadFiles.length === 0) {
    alert('Please upload resumes first.');
    return;
  }

  saveResumesBtn.disabled = true;
  saveResumesBtn.innerHTML = '<span>Saving...</span>';

  try {
    for (const file of uploadFiles) {
      const text = await file.text();
      const contactInfo = extractContactInfo(text);
      const roleInfo = extractCurrentRole(text);

      await saveResumeToLibrary({
        name: file.name.replace(/\.[^/.]+$/, '').split(/[_-]/).map(capitalize).join(' '),
        fileName: file.name,
        content: text,
        resume: text,
        email: contactInfo.email,
        phone: contactInfo.phone,
        linkedin: contactInfo.linkedin,
        location: extractLocation(text),
        experience: extractExperience(text),
        currentRole: roleInfo.currentRole,
        currentCompany: roleInfo.currentCompany,
        education: extractEducation(text)
      });
    }

    await renderLibrary();
    alert(`${uploadFiles.length} resume(s) saved to library.`);

    // Clear the file input
    resumeFiles.value = '';
    refreshFileList([]);

  } catch (error) {
    console.error('Error saving resumes:', error);
    alert('Error saving resumes. Please try again.');
  } finally {
    saveResumesBtn.disabled = false;
    saveResumesBtn.innerHTML = '<span>Save to Library</span>';
  }
}

function toggleSelectAll() {
  const checkboxes = document.querySelectorAll('.library-item-checkbox');
  const allSelected = selectedResumeIds.size === checkboxes.length && checkboxes.length > 0;

  checkboxes.forEach(checkbox => {
    const id = parseInt(checkbox.dataset.id);
    const item = checkbox.closest('.library-item');

    if (allSelected) {
      checkbox.checked = false;
      selectedResumeIds.delete(id);
      item.classList.remove('selected');
    } else {
      checkbox.checked = true;
      selectedResumeIds.add(id);
      item.classList.add('selected');
    }
  });

  selectAllBtn.textContent = allSelected ? 'Select All' : 'Deselect All';
}

async function deleteSelectedResumes() {
  if (selectedResumeIds.size === 0) {
    alert('Please select resumes to delete.');
    return;
  }

  if (!confirm(`Are you sure you want to delete ${selectedResumeIds.size} resume(s)?`)) {
    return;
  }

  try {
    await deleteMultipleResumes(Array.from(selectedResumeIds));
    await renderLibrary();
    selectAllBtn.textContent = 'Select All';
  } catch (error) {
    console.error('Error deleting resumes:', error);
    alert('Error deleting resumes. Please try again.');
  }
}

// Library event listeners
if (saveResumesBtn) {
  saveResumesBtn.addEventListener('click', saveUploadedResumes);
}

if (selectAllBtn) {
  selectAllBtn.addEventListener('click', toggleSelectAll);
}

if (deleteSelectedBtn) {
  deleteSelectedBtn.addEventListener('click', deleteSelectedResumes);
}

if (closeModal) {
  closeModal.addEventListener('click', closeResumeModal);
}

if (resumeModal) {
  resumeModal.addEventListener('click', (e) => {
    if (e.target === resumeModal) {
      closeResumeModal();
    }
  });
}

// Initialize database and load library
async function initializeApp() {
  try {
    await openDatabase();
    await renderLibrary();
  } catch (error) {
    console.error('Error initializing database:', error);
  }
}

// Initialize empty state
updateDashboardMetrics([]);

// Initialize the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}
