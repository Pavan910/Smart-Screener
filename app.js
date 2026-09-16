// =====================
// SMART-SCREENER v5.0 FRONTEND
// Simplified - All extraction handled by backend
// =====================

// =====================
// PASSWORD PROTECTION
// =====================
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
    const response = await fetch('/api/', {
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

  if (loginForm) loginForm.addEventListener('submit', handleLogin);
  if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);

  if (checkAuth()) {
    showApp();
  } else {
    showLogin();
  }
});

// =====================
// MAIN APP
// =====================
const sampleJobDescription = `Senior Data Analyst with strong business communication, SQL, Python, dashboard design, stakeholder management, and experience translating source data into measurable insights for executive decision-making.`;

let currentRankingData = [];
let currentJDAnalysis = null;
const MAX_UPLOAD_LIMIT = 20;

// =====================
// PDF TEXT EXTRACTION
// =====================
if (typeof pdfjsLib !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

async function extractTextFromPDF(file) {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let fullText = '';

    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();
      const pageText = textContent.items.map(item => item.str).join(' ');
      fullText += pageText + '\n';
    }

    return fullText.trim();
  } catch (error) {
    console.error('PDF extraction error:', error);
    return '';
  }
}

async function extractTextFromFile(file) {
  const fileName = file.name.toLowerCase();
  if (fileName.endsWith('.pdf')) {
    return await extractTextFromPDF(file);
  }
  return await file.text();
}

async function getBase64FromFile(file) {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const uint8Array = new Uint8Array(arrayBuffer);
    let binary = '';
    for (let i = 0; i < uint8Array.length; i++) {
      binary += String.fromCharCode(uint8Array[i]);
    }
    return btoa(binary);
  } catch (e) {
    console.warn('Base64 encoding error:', e);
    return '';
  }
}

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

async function saveResumeToLibrary(resume) {
  if (!db) await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.add({ ...resume, savedAt: new Date().toISOString() });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getAllResumes() {
  if (!db) await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getResumeById(id) {
  if (!db) await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.get(id);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function deleteResumeById(id) {
  if (!db) await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.delete(id);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function deleteMultipleResumes(ids) {
  if (!db) await openDatabase();
  return new Promise((resolve, reject) => {
    if (ids.length === 0) { resolve(); return; }
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    let completed = 0;
    ids.forEach(id => {
      const request = store.delete(id);
      request.onsuccess = () => { completed++; if (completed === ids.length) resolve(); };
      request.onerror = () => reject(request.error);
    });
  });
}

// =====================
// DOM ELEMENTS
// =====================
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

// =====================
// HELPER FUNCTIONS
// =====================
function getInitials(name) {
  if (!name) return '??';
  return name.split(' ').map(n => n.slice(0, 1)).slice(0, 2).join('').toUpperCase();
}

function capitalize(value) {
  if (!value) return '';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function getScoreClass(score) {
  if (score >= 85) return 'score-excellent';
  if (score >= 70) return 'score-good';
  if (score >= 50) return 'score-average';
  return 'score-poor';
}

function getRecommendationClass(rec) {
  if (!rec) return 'decision-pool';
  const r = rec.toLowerCase();
  if (r.includes('strong hire')) return 'decision-shortlist';
  if (r.includes('hire')) return 'decision-review';
  if (r.includes('maybe')) return 'decision-average';
  return 'decision-poor';
}

// =====================
// RENDER FUNCTIONS
// =====================
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
    tr.className = 'candidate-row';
    tr.dataset.index = index;

    const rec = item.recommendation || 'Maybe';
    const recClass = getRecommendationClass(rec);
    const skills = Array.isArray(item.skills) ? item.skills.slice(0, 3).join(', ') :
                   (item.coveredSkills ? item.coveredSkills.slice(0, 3).join(', ') : '-');

    tr.innerHTML = `
      <td class="rank-token">${String(index + 1).padStart(2, '0')}</td>
      <td><span class="table-name">${item.name || 'Unknown'}</span></td>
      <td>${item.email || '-'}</td>
      <td>${item.phone || '-'}</td>
      <td>${item.location || '-'}</td>
      <td>${item.experience || 0} yrs</td>
      <td>${item.currentRole || item.title || '-'}</td>
      <td title="${Array.isArray(item.skills) ? item.skills.join(', ') : ''}">${skills || '-'}</td>
      <td><span class="score-number ${getScoreClass(item.score)}">${item.score || 0}</span></td>
      <td><span class="decision ${recClass}">${rec}</span></td>
    `;

    // Click to show detailed report
    tr.addEventListener('click', () => showCandidateDetail(item));
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
  const skills = Array.isArray(top.skills) ? top.skills.slice(0, 5).join(', ') :
                 (top.coveredSkills ? top.coveredSkills.slice(0, 5).join(', ') : 'N/A');

  const scores = top.scores || {};
  const report = top.report || {};

  bestCandidateCard.innerHTML = `
    <div class="candidate-head">
      <div>
        <span class="candidate-avatar">${getInitials(top.name)}</span>
      </div>
      <div>
        <span class="candidate-name">${top.name || 'Unknown'}</span>
        <span class="candidate-title">${top.currentRole || top.title || 'Candidate'}</span>
      </div>
      <span class="candidate-score ${getScoreClass(top.score)}">${top.score || 0}</span>
    </div>
    <div class="candidate-body">
      ${scores.skills !== undefined ? `
      <div class="score-breakdown">
        <div class="score-item">
          <span class="score-label">Skills</span>
          <div class="score-bar-bg"><div class="score-bar-fill" style="width:${scores.skills}%"></div></div>
          <span class="score-value">${scores.skills}%</span>
        </div>
        <div class="score-item">
          <span class="score-label">Experience</span>
          <div class="score-bar-bg"><div class="score-bar-fill" style="width:${scores.experience}%"></div></div>
          <span class="score-value">${scores.experience}%</span>
        </div>
        <div class="score-item">
          <span class="score-label">Education</span>
          <div class="score-bar-bg"><div class="score-bar-fill" style="width:${scores.education}%"></div></div>
          <span class="score-value">${scores.education}%</span>
        </div>
        <div class="score-item">
          <span class="score-label">Career Fit</span>
          <div class="score-bar-bg"><div class="score-bar-fill" style="width:${scores.career_fit}%"></div></div>
          <span class="score-value">${scores.career_fit}%</span>
        </div>
      </div>
      ` : ''}
      <div class="candidate-details">
        <div>
          <span class="candidate-label">Experience</span>
          <span class="candidate-value">${top.experience || 0} years</span>
        </div>
        <div>
          <span class="candidate-label">Skills Match</span>
          <span class="candidate-value">${top.coveredSkills ? top.coveredSkills.length : 0} matched</span>
        </div>
      </div>
      ${report.summary ? `
      <div class="candidate-summary">
        <span class="summary-title">Summary</span>
        <p>${report.summary}</p>
      </div>
      ` : ''}
      ${report.strengths && report.strengths.length > 0 ? `
      <div class="candidate-strengths">
        <span class="strengths-title">Key Strengths</span>
        <ul>${report.strengths.slice(0, 3).map(s => `<li>${s}</li>`).join('')}</ul>
      </div>
      ` : ''}
      <div class="candidate-readiness">
        <span class="readiness-title">Contact</span>
        <span class="readiness-text">${top.email || 'No email available'}</span>
      </div>
    </div>
  `;
}

function showCandidateDetail(candidate) {
  const modal = document.getElementById('candidateModal');
  if (!modal) return;

  const scores = candidate.scores || {};
  const report = candidate.report || {};
  const skills = Array.isArray(candidate.skills) ? candidate.skills : [];
  const coveredSkills = candidate.coveredSkills || [];
  const missingSkills = candidate.missingSkills || [];

  document.getElementById('candidateModalTitle').textContent = candidate.name || 'Candidate';
  document.getElementById('candidateModalContent').innerHTML = `
    <div class="modal-candidate-header">
      <div class="modal-avatar">${getInitials(candidate.name)}</div>
      <div class="modal-info">
        <h3>${candidate.name || 'Unknown'}</h3>
        <p>${candidate.currentRole || candidate.title || 'Candidate'} ${candidate.currentCompany ? 'at ' + candidate.currentCompany : ''}</p>
        <p class="contact-info">${candidate.email || ''} ${candidate.phone ? '| ' + candidate.phone : ''}</p>
      </div>
      <div class="modal-score ${getScoreClass(candidate.score)}">${candidate.score || 0}</div>
    </div>

    <div class="modal-section">
      <h4>Score Breakdown</h4>
      <div class="score-breakdown-grid">
        <div class="breakdown-item">
          <span>Skills</span>
          <div class="breakdown-bar"><div style="width:${scores.skills || 0}%"></div></div>
          <span>${scores.skills || 0}%</span>
        </div>
        <div class="breakdown-item">
          <span>Experience</span>
          <div class="breakdown-bar"><div style="width:${scores.experience || 0}%"></div></div>
          <span>${scores.experience || 0}%</span>
        </div>
        <div class="breakdown-item">
          <span>Education</span>
          <div class="breakdown-bar"><div style="width:${scores.education || 0}%"></div></div>
          <span>${scores.education || 0}%</span>
        </div>
        <div class="breakdown-item">
          <span>Career Fit</span>
          <div class="breakdown-bar"><div style="width:${scores.career_fit || 0}%"></div></div>
          <span>${scores.career_fit || 0}%</span>
        </div>
      </div>
    </div>

    <div class="modal-section">
      <h4>Recommendation</h4>
      <p class="recommendation ${getRecommendationClass(candidate.recommendation)}">${candidate.recommendation || 'N/A'}</p>
      ${candidate.recommendationReason ? `<p class="rec-reason">${candidate.recommendationReason}</p>` : ''}
    </div>

    ${report.summary ? `
    <div class="modal-section">
      <h4>Summary</h4>
      <p>${report.summary}</p>
    </div>
    ` : ''}

    ${report.strengths && report.strengths.length > 0 ? `
    <div class="modal-section">
      <h4>Strengths</h4>
      <ul class="strength-list">${report.strengths.map(s => `<li class="strength-item">${s}</li>`).join('')}</ul>
    </div>
    ` : ''}

    ${report.gaps && report.gaps.length > 0 ? `
    <div class="modal-section">
      <h4>Gaps / Areas to Address</h4>
      <ul class="gap-list">${report.gaps.map(g => `<li class="gap-item">${g}</li>`).join('')}</ul>
    </div>
    ` : ''}

    ${report.risks && report.risks.length > 0 ? `
    <div class="modal-section">
      <h4>Risk Factors</h4>
      <ul class="risk-list">${report.risks.map(r => `<li class="risk-item">${r}</li>`).join('')}</ul>
    </div>
    ` : ''}

    ${report.interviewFocus && report.interviewFocus.length > 0 ? `
    <div class="modal-section">
      <h4>Interview Focus Areas</h4>
      <ul class="focus-list">${report.interviewFocus.map(f => `<li>${f}</li>`).join('')}</ul>
    </div>
    ` : ''}

    <div class="modal-section">
      <h4>Skills</h4>
      <div class="skills-container">
        <div class="skills-group">
          <span class="skills-label">Matched (${coveredSkills.length})</span>
          <div class="skill-tags matched">
            ${coveredSkills.map(s => `<span class="skill-tag matched">${s}</span>`).join('')}
          </div>
        </div>
        ${missingSkills.length > 0 ? `
        <div class="skills-group">
          <span class="skills-label">Missing (${missingSkills.length})</span>
          <div class="skill-tags missing">
            ${missingSkills.map(s => `<span class="skill-tag missing">${s}</span>`).join('')}
          </div>
        </div>
        ` : ''}
      </div>
    </div>

    <div class="modal-section">
      <h4>Details</h4>
      <div class="details-grid">
        <div><strong>Experience:</strong> ${candidate.experience || 0} years</div>
        <div><strong>Education:</strong> ${candidate.education || 'N/A'}</div>
        <div><strong>Location:</strong> ${candidate.location || 'N/A'}</div>
        <div><strong>LinkedIn:</strong> ${candidate.linkedin ? `<a href="${candidate.linkedin}" target="_blank">View Profile</a>` : 'N/A'}</div>
      </div>
    </div>
  `;

  modal.style.display = 'flex';
}

function closeCandidateModal() {
  const modal = document.getElementById('candidateModal');
  if (modal) modal.style.display = 'none';
}

function updateDashboardMetrics(ranking) {
  const metricScanned = document.getElementById('metricScanned');
  const metricTopScore = document.getElementById('metricTopScore');
  const metricCoverage = document.getElementById('metricCoverage');
  const metricShortlist = document.getElementById('metricShortlist');

  if (!ranking || ranking.length === 0) {
    if (metricScanned) metricScanned.textContent = '00';
    if (metricTopScore) metricTopScore.textContent = '--';
    if (metricCoverage) metricCoverage.textContent = '--';
    if (metricShortlist) metricShortlist.textContent = '00';
    return;
  }

  const sorted = [...ranking].sort((a, b) => b.score - a.score);
  const top = sorted[0];
  const total = ranking.length;
  const shortlisted = ranking.filter(item => item.score >= 75).length;
  const avgScore = Math.round(ranking.reduce((sum, r) => sum + (r.score || 0), 0) / total);

  if (metricScanned) metricScanned.textContent = String(total).padStart(2, '0');
  if (metricTopScore) metricTopScore.textContent = String(top.score || 0);
  if (metricCoverage) metricCoverage.textContent = avgScore + '%';
  if (metricShortlist) metricShortlist.textContent = String(shortlisted).padStart(2, '0');
}

function refreshFileList(files, showLimitWarning = false) {
  fileList.innerHTML = '';

  if (files.length === 0) {
    fileList.innerHTML = '<div class="empty-files">No resumes selected</div>';
    uploadStatus.textContent = '0 files';
    return;
  }

  if (files.length > MAX_UPLOAD_LIMIT) {
    if (showLimitWarning) {
      alert(`Upload limit exceeded. Maximum ${MAX_UPLOAD_LIMIT} resumes allowed.`);
    }
    fileList.innerHTML = `<div class="empty-files" style="color: #dc3545;">Too many files (${files.length}). Max ${MAX_UPLOAD_LIMIT}.</div>`;
    uploadStatus.textContent = `${files.length} files (limit: ${MAX_UPLOAD_LIMIT})`;
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

// =====================
// MAIN ANALYSIS
// =====================
async function runAnalysis(includeLibraryResumes = false) {
  const jobText = jobDescription.value;

  if (!jobText.trim()) {
    alert('Please enter a job description first.');
    return;
  }

  const uploadFiles = Array.from(resumeFiles.files);
  const hasUploadedFiles = uploadFiles.length > 0;
  const hasSelectedLibrary = includeLibraryResumes && selectedResumeIds.size > 0;

  if (!hasUploadedFiles && !hasSelectedLibrary) {
    alert('Please upload resumes or select from library.');
    return;
  }

  const totalCount = uploadFiles.length + (hasSelectedLibrary ? selectedResumeIds.size : 0);
  if (totalCount > MAX_UPLOAD_LIMIT) {
    alert(`Too many resumes. Maximum ${MAX_UPLOAD_LIMIT} allowed.`);
    return;
  }

  // Update UI
  scanButton.disabled = true;
  scanButton.innerHTML = '<span>Analyzing...</span>';
  if (scanSelectedBtn) scanSelectedBtn.disabled = true;

  const allResumes = [];

  // Process uploaded files - only extract text, let backend handle parsing
  for (const file of uploadFiles) {
    const text = await extractTextFromFile(file);
    let pdfData = '';
    if (file.name.toLowerCase().endsWith('.pdf')) {
      pdfData = await getBase64FromFile(file);
    }

    // Send minimal data - backend handles all extraction
    allResumes.push({
      name: file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' '),
      resume: text,
      pdfData: pdfData
    });
  }

  // Add library resumes
  if (hasSelectedLibrary) {
    for (const id of selectedResumeIds) {
      const resume = await getResumeById(id);
      if (resume) {
        allResumes.push({
          name: resume.name || 'Unknown',
          resume: resume.content || resume.resume || ''
        });
      }
    }
  }

  if (allResumes.length === 0) {
    alert('Could not extract text from any resumes.');
    resetScanButton();
    return;
  }

  try {
    const response = await fetch('/api/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jobDescription: jobText,
        resumes: allResumes
      })
    });

    if (!response.ok) throw new Error(`API returned ${response.status}`);

    const result = await response.json();

    if (result.error) {
      alert(result.error);
      resetScanButton();
      return;
    }

    currentRankingData = result.ranking || [];
    currentJDAnalysis = result.jd_analysis || null;

    renderRankings(currentRankingData);
    renderResultsTable(currentRankingData);
    renderBestCandidate(currentRankingData);
    updateDashboardMetrics(currentRankingData);

    // Show metadata
    if (result.metadata) {
      console.log('Analysis metadata:', result.metadata);
    }

  } catch (error) {
    console.error('Analysis error:', error);
    alert('Error analyzing resumes. Please try again.');
  } finally {
    resetScanButton();
  }
}

function resetScanButton() {
  scanButton.disabled = false;
  scanButton.innerHTML = '<span>Scan Resumes</span>';
  if (scanSelectedBtn) scanSelectedBtn.disabled = false;
}

async function scanSelectedResumes() {
  if (selectedResumeIds.size === 0) {
    alert('Please select resumes from the library.');
    return;
  }
  await runAnalysis(true);
}

// =====================
// EXPORT FUNCTIONS
// =====================
function exportToCSV() {
  if (currentRankingData.length === 0) {
    alert('No data to export.');
    return;
  }

  const headers = ['Name', 'Email', 'Phone', 'Location', 'Experience', 'Current Role', 'Skills', 'Score', 'Recommendation'];
  const rows = currentRankingData.map(r => [
    r.name || '',
    r.email || '',
    r.phone || '',
    r.location || '',
    r.experience || 0,
    r.currentRole || r.title || '',
    Array.isArray(r.skills) ? r.skills.join('; ') : '',
    r.score || 0,
    r.recommendation || ''
  ]);

  const csvContent = [headers, ...rows]
    .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  downloadFile(csvContent, 'candidates-report.csv', 'text/csv');
}

function exportToExcel() {
  if (currentRankingData.length === 0) {
    alert('No data to export.');
    return;
  }

  const headers = ['Name', 'Email', 'Phone', 'Location', 'Experience', 'Current Role', 'Skills', 'Score', 'Recommendation', 'Strengths', 'Gaps'];
  const rows = currentRankingData.map(r => [
    r.name || '',
    r.email || '',
    r.phone || '',
    r.location || '',
    r.experience || 0,
    r.currentRole || r.title || '',
    Array.isArray(r.skills) ? r.skills.join('; ') : '',
    r.score || 0,
    r.recommendation || '',
    r.report?.strengths ? r.report.strengths.join('; ') : '',
    r.report?.gaps ? r.report.gaps.join('; ') : ''
  ]);

  const content = [headers, ...rows]
    .map(row => row.map(cell => String(cell).replace(/\t/g, ' ')).join('\t'))
    .join('\n');

  downloadFile(content, 'candidates-report.xls', 'application/vnd.ms-excel');
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType + ';charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

// =====================
// EVENT LISTENERS
// =====================
scanButton.addEventListener('click', () => runAnalysis(true));
loadJobButton.addEventListener('click', () => { jobDescription.value = sampleJobDescription; });

clearFiles.addEventListener('click', () => {
  resumeFiles.value = '';
  refreshFileList([]);
  currentRankingData = [];
  currentJDAnalysis = null;
  renderRankings([]);
  renderResultsTable([]);
  renderBestCandidate([]);
  updateDashboardMetrics([]);
});

resumeFiles.addEventListener('change', event => {
  refreshFileList(Array.from(event.target.files), true);
});

exportCsvBtn.addEventListener('click', exportToCSV);
exportExcelBtn.addEventListener('click', exportToExcel);

refreshBtn.addEventListener('click', () => {
  if (resumeFiles.files.length > 0 || selectedResumeIds.size > 0) {
    runAnalysis(true);
  }
});

// Drag and drop
dropZone.addEventListener('click', () => resumeFiles.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.style.borderColor = '#246b68'; });
dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = '#dae7e8'; });
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.style.borderColor = '#dae7e8';
  resumeFiles.files = e.dataTransfer.files;
  refreshFileList(Array.from(e.dataTransfer.files), true);
});

// Candidate modal close
document.addEventListener('click', e => {
  const modal = document.getElementById('candidateModal');
  if (e.target === modal) closeCandidateModal();
  if (e.target.id === 'closeCandidateModal') closeCandidateModal();
});

// =====================
// LIBRARY FUNCTIONALITY
// =====================
const libraryGrid = document.getElementById('libraryGrid');
const libraryCount = document.getElementById('libraryCount');
const saveResumesBtn = document.getElementById('saveResumesBtn');
const selectAllBtn = document.getElementById('selectAllBtn');
const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
const scanSelectedBtn = document.getElementById('scanSelectedBtn');
const resumeModal = document.getElementById('resumeModal');
const closeModal = document.getElementById('closeModal');

let selectedResumeIds = new Set();
const MAX_STORAGE_MB = 100;

function updateLibraryCount(count) {
  if (libraryCount) libraryCount.textContent = count;
}

function calculateStorageSize(resumes) {
  let totalBytes = 0;
  resumes.forEach(resume => {
    const content = resume.content || resume.resume || '';
    totalBytes += new Blob([content]).size;
    totalBytes += 500; // Estimate for metadata
  });
  return totalBytes;
}

function updateStorageIndicator(resumes) {
  const totalBytes = calculateStorageSize(resumes);
  const totalMB = totalBytes / (1024 * 1024);
  const percentage = Math.min(100, (totalMB / MAX_STORAGE_MB) * 100);

  const storageUsed = document.getElementById('storageUsed');
  const storageBar = document.getElementById('storageBar');
  const storagePercent = document.getElementById('storagePercent');

  if (storageUsed) storageUsed.textContent = totalMB.toFixed(2) + ' MB';
  if (storageBar) {
    storageBar.style.width = percentage + '%';
    storageBar.className = 'progress-bar ' + (percentage >= 90 ? 'storage-critical' : percentage >= 70 ? 'storage-warning' : 'storage-ok');
  }
  if (storagePercent) storagePercent.textContent = Math.round(percentage) + '%';
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

async function renderLibrary() {
  try {
    const resumes = await getAllResumes();
    updateLibraryCount(resumes.length);
    updateStorageIndicator(resumes);
    selectedResumeIds.clear();

    if (resumes.length === 0) {
      libraryGrid.innerHTML = '<div class="empty-state">No resumes in library.</div>';
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
        <div class="library-item-meta">Saved: ${formatDate(resume.savedAt)}</div>
        <div class="library-item-actions">
          <button class="library-item-btn view-btn" data-id="${resume.id}">View</button>
          <button class="library-item-btn danger delete-btn" data-id="${resume.id}">Delete</button>
        </div>
      `;
      libraryGrid.appendChild(item);
    });

    // Event listeners
    document.querySelectorAll('.library-item-checkbox').forEach(cb => {
      cb.addEventListener('change', e => {
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
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        const resume = await getResumeById(parseInt(e.target.dataset.id));
        if (resume && resumeModal) {
          document.getElementById('modalTitle').textContent = resume.name || 'Resume';
          document.getElementById('resumeContent').textContent = resume.content || resume.resume || 'No content';
          resumeModal.style.display = 'flex';
        }
      });
    });

    document.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        if (confirm('Delete this resume?')) {
          await deleteResumeById(parseInt(e.target.dataset.id));
          await renderLibrary();
        }
      });
    });
  } catch (error) {
    console.error('Library error:', error);
    libraryGrid.innerHTML = '<div class="empty-state">Error loading library.</div>';
  }
}

async function saveUploadedResumes() {
  const files = Array.from(resumeFiles.files);
  if (files.length === 0) { alert('Please upload resumes first.'); return; }
  if (files.length > MAX_UPLOAD_LIMIT) { alert(`Maximum ${MAX_UPLOAD_LIMIT} resumes allowed.`); return; }

  saveResumesBtn.disabled = true;
  saveResumesBtn.innerHTML = '<span>Saving...</span>';

  try {
    for (const file of files) {
      const text = await extractTextFromFile(file);
      if (!text || text.trim().length < 50) continue;

      await saveResumeToLibrary({
        name: file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' '),
        fileName: file.name,
        content: text
      });
    }
    await renderLibrary();
    alert(`${files.length} resume(s) saved to library.`);
    resumeFiles.value = '';
    refreshFileList([]);
  } catch (error) {
    console.error('Save error:', error);
    alert('Error saving resumes.');
  } finally {
    saveResumesBtn.disabled = false;
    saveResumesBtn.innerHTML = '<span>Save to Library</span>';
  }
}

function toggleSelectAll() {
  const checkboxes = document.querySelectorAll('.library-item-checkbox');
  const allSelected = selectedResumeIds.size === checkboxes.length && checkboxes.length > 0;

  checkboxes.forEach(cb => {
    const id = parseInt(cb.dataset.id);
    const item = cb.closest('.library-item');
    cb.checked = !allSelected;
    if (!allSelected) {
      selectedResumeIds.add(id);
      item.classList.add('selected');
    } else {
      selectedResumeIds.delete(id);
      item.classList.remove('selected');
    }
  });

  selectAllBtn.textContent = allSelected ? 'Select All' : 'Deselect All';
}

async function deleteSelectedResumes() {
  if (selectedResumeIds.size === 0) { alert('Select resumes to delete.'); return; }
  if (!confirm(`Delete ${selectedResumeIds.size} resume(s)?`)) return;

  await deleteMultipleResumes(Array.from(selectedResumeIds));
  await renderLibrary();
  selectAllBtn.textContent = 'Select All';
}

// Library event listeners
if (saveResumesBtn) saveResumesBtn.addEventListener('click', saveUploadedResumes);
if (selectAllBtn) selectAllBtn.addEventListener('click', toggleSelectAll);
if (deleteSelectedBtn) deleteSelectedBtn.addEventListener('click', deleteSelectedResumes);
if (scanSelectedBtn) scanSelectedBtn.addEventListener('click', scanSelectedResumes);
if (closeModal) closeModal.addEventListener('click', () => { resumeModal.style.display = 'none'; });
if (resumeModal) resumeModal.addEventListener('click', e => { if (e.target === resumeModal) resumeModal.style.display = 'none'; });

// Initialize
async function initializeApp() {
  try {
    await openDatabase();
    await renderLibrary();
  } catch (error) {
    console.error('Init error:', error);
  }
}

updateDashboardMetrics([]);

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}
