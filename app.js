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
    const response = await fetch('/api/rank', {
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

// Maximum number of resumes per upload
const MAX_UPLOAD_LIMIT = 20;

// =====================
// PDF TEXT EXTRACTION
// =====================

// Initialize PDF.js worker
if (typeof pdfjsLib !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

/**
 * Extract text content from a PDF file
 * @param {File} file - The PDF file to extract text from
 * @returns {Promise<string>} - The extracted text content
 */
async function extractTextFromPDF(file) {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

    let fullText = '';

    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();

      // Extract text items and join them
      const pageText = textContent.items
        .map(item => item.str)
        .join(' ');

      fullText += pageText + '\n';
    }

    return fullText.trim();
  } catch (error) {
    console.error('Error extracting PDF text:', error);
    return '';
  }
}

/**
 * Extract text from any supported file type
 * @param {File} file - The file to extract text from
 * @returns {Promise<string>} - The extracted text content
 */
async function extractTextFromFile(file) {
  const fileName = file.name.toLowerCase();

  if (fileName.endsWith('.pdf')) {
    // Use PDF.js for PDF files
    return await extractTextFromPDF(file);
  } else if (fileName.endsWith('.txt') || fileName.endsWith('.html')) {
    // Plain text files
    return await file.text();
  } else if (fileName.endsWith('.doc') || fileName.endsWith('.docx')) {
    // For DOC/DOCX, we can't parse them in browser without additional libraries
    // Return empty and show warning
    console.warn('DOC/DOCX files require conversion. Please use PDF or TXT format.');
    return await file.text(); // This won't work well for binary formats
  } else {
    // Try to read as text
    return await file.text();
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
  // Ensure database is initialized
  if (!db) {
    await openDatabase();
  }

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.add({
        ...resume,
        savedAt: new Date().toISOString()
      });

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

async function getAllResumes() {
  // Ensure database is initialized
  if (!db) {
    await openDatabase();
  }

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

async function getResumeById(id) {
  if (!db) {
    await openDatabase();
  }

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(id);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

async function deleteResumeById(id) {
  if (!db) {
    await openDatabase();
  }

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(id);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

async function deleteMultipleResumes(ids) {
  if (!db) {
    await openDatabase();
  }

  return new Promise((resolve, reject) => {
    try {
      if (ids.length === 0) {
        resolve();
        return;
      }

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
    } catch (error) {
      reject(error);
    }
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

// Extract candidate name from resume text
function extractCandidateName(text, fileName) {
  // Clean and normalize text - PDF extraction often has weird spacing
  const lines = text.split(/\n/).map(l => l.replace(/\s+/g, ' ').trim()).filter(l => l.length > 0);

  // Words that should not be in a name
  const skipWords = ['resume', 'cv', 'curriculum', 'vitae', 'updated', 'profile', 'contact', 'summary', 'objective', 'experience', 'education', 'skills', 'about', 'new', 'final', 'latest'];

  // Try to find name in first lines (usually at the top of resume)
  for (let i = 0; i < Math.min(lines.length, 15); i++) {
    const line = lines[i];

    // Skip lines that look like headers, emails, phones, or URLs
    if (line.match(/^(resume|curriculum|cv|profile|summary|objective|contact|address|phone|email|linkedin|professional|experience|education|skills)/i)) continue;
    if (line.match(/@|http|www\.|\.com|\.org|\.net|\.in\//i)) continue;
    if (line.match(/^\+?\d[\d\s\-().]{6,}/)) continue; // Phone numbers
    if (line.length > 50) continue; // Too long to be just a name
    if (line.length < 3) continue; // Too short

    // Clean the line - remove special chars at start/end
    const cleanLine = line.replace(/^[\s|•\-:]+|[\s|•\-:]+$/g, '').trim();

    // Filter out non-name words
    const words = cleanLine.split(/\s+/).filter(w => w.length > 0);
    const nameWords = words.filter(w => !skipWords.includes(w.toLowerCase()));

    if (nameWords.length >= 2 && nameWords.length <= 4) {
      // Check if words look like name parts (start with capital, only letters)
      const looksLikeName = nameWords.every(w => /^[A-Z][a-zA-Z]*$/.test(w));
      if (looksLikeName) {
        return nameWords.join(' ');
      }
    }

    // Also try: "Name: John Doe" format
    const labeledName = line.match(/^(?:name|candidate|applicant)\s*[:\-]\s*(.+)/i);
    if (labeledName) {
      return labeledName[1].trim();
    }
  }

  // Fallback to cleaned filename - but remove common words
  const fileNameClean = fileName
    .replace(/\.[^/.]+$/, '')  // Remove extension
    .split(/[_\-\s]+/)
    .filter(w => !skipWords.includes(w.toLowerCase()))
    .map(capitalize)
    .join(' ');

  return fileNameClean || 'Unknown';
}

// Extract contact info from resume text
function extractContactInfo(text) {
  // Normalize text for better matching
  const normalizedText = text.replace(/\s+/g, ' ');

  // Better email pattern
  const emailMatch = normalizedText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);

  // Better phone patterns - handles various formats including spaces
  const phonePatterns = [
    /\+91[\s\-]?\d{4}[\s\-]?\d{3}[\s\-]?\d{3}/, // Indian: +91 6351 182 302
    /\+91[\s\-]?\d{5}[\s\-]?\d{5}/, // Indian: +91 63511 82302
    /\+91[\s\-]?[6-9]\d{9}/, // Indian: +91 6351182302
    /[6-9]\d{4}[\s\-]?\d{3}[\s\-]?\d{3}/, // Indian without +91: 6351 182 302
    /[6-9]\d{9}/, // Indian 10 digits
    /\+1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}/, // US format
    /\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}/, // US without +1
    /\+\d{1,3}[\s\-]?\d{6,14}/ // International
  ];

  let phone = '';
  for (const pattern of phonePatterns) {
    const match = normalizedText.match(pattern);
    if (match) {
      // Clean up the phone number - remove spaces but keep + if present
      phone = match[0].replace(/[\s\-]/g, '');
      break;
    }
  }

  // LinkedIn - handle various formats
  const linkedinPatterns = [
    /linkedin\.com\/in\/([a-zA-Z0-9_-]+)/i,
    /linkedin:\s*(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/([a-zA-Z0-9_-]+)/i,
    /linkedin\s*[:\|]\s*([a-zA-Z0-9_-]+)/i
  ];

  let linkedin = '';
  for (const pattern of linkedinPatterns) {
    const match = normalizedText.match(pattern);
    if (match) {
      linkedin = 'https://linkedin.com/in/' + match[1];
      break;
    }
  }

  return {
    email: emailMatch ? emailMatch[0] : '',
    phone: phone,
    linkedin: linkedin
  };
}

// Extract location from resume text
function extractLocation(text) {
  const normalizedText = text.replace(/\s+/g, ' ');
  const textLower = normalizedText.toLowerCase();

  // Extended list of Indian cities
  const indianCities = [
    'Mumbai', 'Delhi', 'New Delhi', 'Bangalore', 'Bengaluru', 'Hyderabad', 'Chennai',
    'Kolkata', 'Pune', 'Ahmedabad', 'Jaipur', 'Noida', 'Gurgaon', 'Gurugram',
    'Vadodara', 'Baroda', 'Surat', 'Lucknow', 'Chandigarh', 'Indore', 'Bhopal',
    'Coimbatore', 'Kochi', 'Cochin', 'Trivandrum', 'Thiruvananthapuram', 'Mysore',
    'Mysuru', 'Nagpur', 'Patna', 'Ranchi', 'Bhubaneswar', 'Visakhapatnam', 'Vizag',
    'Thane', 'Navi Mumbai', 'Faridabad', 'Ghaziabad', 'Rajkot', 'Nashik', 'Aurangabad',
    'Ludhiana', 'Amritsar', 'Agra', 'Varanasi', 'Kanpur', 'Dehradun', 'Raipur',
    'Jodhpur', 'Udaipur', 'Guwahati', 'Mangalore', 'Mangaluru', 'Hubli', 'Belgaum',
    'Salem', 'Madurai', 'Trichy', 'Tiruchirappalli', 'Vijayawada', 'Warangal'
  ];

  // First check for labeled locations
  const labeledPatterns = [
    /(?:Location|Address|City|Based in|residing at|located at|current location)\s*[:\-]\s*([A-Za-z\s,]+)/i,
    /(?:Location|Address)\s*[:\-]?\s*([A-Za-z]+(?:,?\s*[A-Za-z]+)?)/i
  ];

  for (const pattern of labeledPatterns) {
    const match = normalizedText.match(pattern);
    if (match && match[1]) {
      const loc = match[1].trim().split(',')[0].trim();
      if (loc.length > 2 && loc.length < 30) {
        return loc;
      }
    }
  }

  // Check for Indian cities
  for (const city of indianCities) {
    if (textLower.includes(city.toLowerCase())) {
      return city;
    }
  }

  // Check for US cities with state codes
  const usPattern = /([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*(CA|NY|TX|FL|WA|IL|PA|OH|GA|NC|MI|NJ|VA|AZ|MA|TN|IN|MO|MD|WI|CO|MN|SC|AL|LA|KY|OR|OK|CT|UT|IA|NV|AR|MS|KS|NM|NE|WV|ID|HI|NH|ME|MT|RI|DE|SD|ND|AK|VT|WY|DC)/;
  const usMatch = normalizedText.match(usPattern);
  if (usMatch) {
    return `${usMatch[1]}, ${usMatch[2]}`;
  }

  // Check for Remote/Hybrid
  if (textLower.includes('remote') || textLower.includes('work from home')) {
    return 'Remote';
  }

  return '';
}

// Extract experience info - more robust
function extractExperience(text) {
  // First try explicit experience mentions
  const patterns = [
    /(\d+)\+?\s*(?:years?|yrs?)[\s\w]*(?:of\s+)?(?:experience|exp)/i,
    /(?:experience|exp)[\s:]*(\d+)\+?\s*(?:years?|yrs?)/i,
    /(?:total|overall)[\s\w]*(\d+)\+?\s*(?:years?|yrs?)/i,
    /(\d+)\+?\s*(?:years?|yrs?)[\s\w]*(?:professional|work|industry)/i
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return parseInt(match[1]);
  }

  // Calculate from work history dates
  const currentYear = new Date().getFullYear();
  const datePatterns = [
    /(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]*(\d{4})\s*[-–]\s*(?:present|current|now)/gi,
    /(\d{1,2}\/\d{4})\s*[-–]\s*(?:present|current|now)/gi,
    /(\d{4})\s*[-–]\s*(?:present|current|now)/gi
  ];

  let earliestYear = currentYear;
  for (const pattern of datePatterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const year = parseInt(match[1].length === 4 ? match[1] : match[1].split('/')[1]);
      if (year >= 1990 && year <= currentYear && year < earliestYear) {
        earliestYear = year;
      }
    }
  }

  // Also look for date ranges in work history
  const rangePattern = /(\d{4})\s*[-–]\s*(\d{4}|present|current|now)/gi;
  let match;
  while ((match = rangePattern.exec(text)) !== null) {
    const startYear = parseInt(match[1]);
    if (startYear >= 1990 && startYear <= currentYear && startYear < earliestYear) {
      earliestYear = startYear;
    }
  }

  if (earliestYear < currentYear) {
    return currentYear - earliestYear;
  }

  return 0;
}

// Extract current role and company - improved
function extractCurrentRole(text) {
  const lines = text.split(/\n/).map(l => l.replace(/\s+/g, ' ').trim()).filter(l => l.length > 0);
  let currentRole = '';
  let currentCompany = '';

  // Job title keywords that should appear at the START of a title
  const titleStarters = '(?:Senior|Junior|Lead|Principal|Staff|Chief|Head|Director|Manager|Associate|Assistant|Vice|Deputy|Executive|Trainee|Intern)';

  // Core job roles
  const coreRoles = '(?:Engineer|Developer|Analyst|Specialist|Consultant|Architect|Designer|Coordinator|Administrator|Officer|Accountant|Advisor|Representative|Recruiter|Executive|Programmer|Scientist|Researcher)';

  // Domain prefixes
  const domains = '(?:Software|Data|Product|Project|Business|Marketing|Sales|HR|Human Resources|Operations|Quality|Technical|IT|Web|Mobile|Full[\\s-]?Stack|Front[\\s-]?End|Back[\\s-]?End|Financial|Finance|Machine Learning|ML|AI|DevOps|Cloud|Security|Network|Database|System|UX|UI|QA|Test|Support|Customer|Client)';

  // Specific job title patterns - must be complete titles, not part of sentences
  const titlePatterns = [
    // "Senior Software Engineer" or "Data Analyst"
    new RegExp(`^(${titleStarters}\\s+)?${domains}\\s+${coreRoles}$`, 'i'),
    // "Software Engineer - Senior" or "Engineer, Software"
    new RegExp(`^${domains}\\s+${coreRoles}(?:\\s*[-–,]\\s*${titleStarters})?$`, 'i'),
    // "ML Engineer" or "AI Specialist"
    new RegExp(`^(${titleStarters}\\s+)?(?:ML|AI|SDE|SWE|MTS)(?:\\s+${coreRoles})?$`, 'i'),
    // Role at Company format: "Software Engineer at Google"
    new RegExp(`^(${titleStarters}\\s+)?${domains}?\\s*${coreRoles}\\s+(?:at|@)\\s+[A-Z]`, 'i'),
    // Simple role titles
    /^(Software Engineer|Data Analyst|Product Manager|Project Manager|Business Analyst|HR Manager|Financial Analyst|Data Scientist|ML Engineer|DevOps Engineer|Full Stack Developer|Frontend Developer|Backend Developer|QA Engineer|Test Engineer|System Administrator|Network Engineer|Cloud Engineer|Security Analyst|UX Designer|UI Designer|Technical Lead|Team Lead|Tech Lead|Engineering Manager|Scrum Master|Agile Coach)$/i
  ];

  // Look for work experience section first
  let inWorkSection = false;
  let foundInWorkSection = false;

  for (let i = 0; i < Math.min(lines.length, 60); i++) {
    const line = lines[i];

    // Check if entering work experience section
    if (line.match(/^(work\s*experience|professional\s*experience|employment\s*history|career\s*history|experience)/i)) {
      inWorkSection = true;
      continue;
    }

    // Skip section headers
    if (line.match(/^(education|skills|certifications|projects|achievements|summary|objective|contact|references)/i)) {
      inWorkSection = false;
      continue;
    }

    if (inWorkSection && !foundInWorkSection) {
      // Look for role with date pattern: "Software Engineer | Jan 2020 - Present"
      const roleWithDate = line.match(/^([A-Za-z\s\-]+(?:Engineer|Developer|Analyst|Manager|Specialist|Consultant|Designer|Lead|Architect|Officer|Coordinator|Administrator|Executive|Scientist|Recruiter|Representative|Accountant))\s*[|–\-]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present)/i);
      if (roleWithDate) {
        currentRole = roleWithDate[1].trim();
        foundInWorkSection = true;
        continue;
      }

      // Check for company name with date
      const companyPattern = line.match(/^([A-Z][A-Za-z\s&.,]+(?:Ltd|Inc|Corp|LLC|Pvt|Private|Limited|Company|Technologies|Solutions|Services|Consulting)?)\s*[|–\-]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})/i);
      if (companyPattern && !currentCompany) {
        currentCompany = companyPattern[1].trim();
      }

      // Check next line for role if we found company
      if (currentCompany && !currentRole && lines[i + 1]) {
        const nextLine = lines[i + 1].trim();
        for (const pattern of titlePatterns) {
          if (pattern.test(nextLine)) {
            currentRole = nextLine;
            foundInWorkSection = true;
            break;
          }
        }
      }
    }

    // Also look for standalone job titles (often near the top)
    if (!currentRole && i < 20) {
      for (const pattern of titlePatterns) {
        if (pattern.test(line) && line.length < 60) {
          currentRole = line;
          break;
        }
      }
    }
  }

  // Clean up the role
  if (currentRole) {
    currentRole = currentRole
      .replace(/[•\-–|]\s*$/, '')
      .replace(/\s+/g, ' ')
      .trim();

    // Limit length and ensure it looks like a title
    if (currentRole.length > 50) {
      currentRole = currentRole.substring(0, 50).replace(/\s+\S*$/, '');
    }
  }

  return { currentRole, currentCompany };
}

// Extract education - improved
function extractEducation(text) {
  const normalizedText = text.replace(/\s+/g, ' ');

  const eduPatterns = [
    // Full degree with field - "Bachelor of Commerce (B.Com)"
    /(Bachelor\s+of\s+[A-Za-z\s]+(?:\([^)]+\))?)/i,
    /(Master\s+of\s+[A-Za-z\s]+(?:\([^)]+\))?)/i,
    // Short forms - B.Com, B.Tech, M.Tech, etc.
    /(B\.?Com|B\.?Tech|M\.?Tech|B\.?E|M\.?E|B\.?Sc|M\.?Sc|BCA|MCA|BBA|MBA|B\.?A|M\.?A|B\.?S|M\.?S|PhD|Ph\.D)/i,
    // Degree patterns
    /((?:Bachelor|Master|Doctor|PhD|Ph\.D|MBA)[^.\n,]{0,50})/i,
    // University names
    /((?:University|Institute|College)\s+of\s+[A-Za-z\s]{3,30}|IIT\s*[A-Za-z]*|IIM\s*[A-Za-z]*|NIT\s*[A-Za-z]*|BITS\s*[A-Za-z]*)/i
  ];

  for (const pattern of eduPatterns) {
    const match = normalizedText.match(pattern);
    if (match) {
      let education = match[1] ? match[1].trim() : match[0].trim();
      // Limit length
      if (education.length > 60) {
        education = education.substring(0, 60);
      }
      return education;
    }
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
    // Use backend recommendation or calculate based on score
    let decision = item.recommendation || (item.score >= 80 ? 'Best' : item.score >= 65 ? 'Good' : item.score >= 50 ? 'Average' : 'Poor');
    let decisionClass = 'decision-pool';
    if (decision === 'Best' || item.score >= 80) {
      decisionClass = 'decision-shortlist';
      decision = 'Best';
    } else if (decision === 'Good' || item.score >= 65) {
      decisionClass = 'decision-review';
      decision = 'Good';
    } else if (decision === 'Average' || item.score >= 50) {
      decisionClass = 'decision-average';
      decision = 'Average';
    } else {
      decisionClass = 'decision-poor';
      decision = 'Poor';
    }
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
  const shortlisted = ranking.filter(item => item.score >= 85).length;
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

  // Check upload limit
  if (files.length > MAX_UPLOAD_LIMIT) {
    if (showLimitWarning) {
      alert(`Upload limit exceeded. Maximum ${MAX_UPLOAD_LIMIT} resumes allowed per upload. You selected ${files.length} files.`);
    }
    fileList.innerHTML = `<div class="empty-files" style="color: #dc3545;">Too many files selected (${files.length}). Maximum ${MAX_UPLOAD_LIMIT} allowed.</div>`;
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

async function runAnalysis(includeLibraryResumes = false) {
  const jobText = jobDescription.value;

  if (!jobText.trim()) {
    alert('Please enter a job description first.');
    return;
  }

  const uploadFiles = Array.from(resumeFiles.files);
  const hasUploadedFiles = uploadFiles.length > 0;
  const hasSelectedLibrary = includeLibraryResumes && selectedResumeIds.size > 0;

  // Check if we have any resumes to scan
  if (!hasUploadedFiles && !hasSelectedLibrary) {
    alert('Please upload resumes or select resumes from the library to scan.');
    return;
  }

  // Check total count against limit
  const totalCount = uploadFiles.length + (hasSelectedLibrary ? selectedResumeIds.size : 0);
  if (totalCount > MAX_UPLOAD_LIMIT) {
    alert(`Too many resumes selected. Maximum ${MAX_UPLOAD_LIMIT} allowed. You have ${totalCount} total (${uploadFiles.length} uploaded + ${selectedResumeIds.size} from library).`);
    return;
  }

  scanButton.disabled = true;
  scanButton.innerHTML = '<span>Scanning...</span>';
  if (scanSelectedBtn) {
    scanSelectedBtn.disabled = true;
  }

  const allResumes = [];

  // Process uploaded files
  try {
    for (const file of uploadFiles) {
      const text = await extractTextFromFile(file);

      // Get base64 PDF data for server-side extraction (better quality)
      let pdfData = '';
      if (file.name.toLowerCase().endsWith('.pdf')) {
        try {
          const arrayBuffer = await file.arrayBuffer();
          const uint8Array = new Uint8Array(arrayBuffer);
          let binary = '';
          for (let i = 0; i < uint8Array.length; i++) {
            binary += String.fromCharCode(uint8Array[i]);
          }
          pdfData = btoa(binary);
        } catch (e) {
          console.warn('Could not encode PDF to base64:', e);
        }
      }

      const contactInfo = extractContactInfo(text);
      const roleInfo = extractCurrentRole(text);
      const candidateName = extractCandidateName(text, file.name);

      allResumes.push({
        name: candidateName,
        resume: text,
        pdfData: pdfData,  // Send base64 PDF for server-side extraction
        email: contactInfo.email,
        phone: contactInfo.phone,
        linkedin: contactInfo.linkedin,
        location: extractLocation(text),
        experience: extractExperience(text),
        currentRole: roleInfo.currentRole,
        currentCompany: roleInfo.currentCompany,
        education: extractEducation(text),
        source: 'upload'
      });
    }
  } catch (error) {
    console.warn('Error reading uploaded files:', error);
  }

  // Add selected library resumes
  if (hasSelectedLibrary) {
    try {
      for (const id of selectedResumeIds) {
        const resume = await getResumeById(id);
        if (resume) {
          allResumes.push({
            name: resume.name || 'Unknown',
            resume: resume.content || resume.resume || '',
            email: resume.email || '',
            phone: resume.phone || '',
            linkedin: resume.linkedin || '',
            location: resume.location || '',
            experience: resume.experience || 0,
            currentRole: resume.currentRole || '',
            currentCompany: resume.currentCompany || '',
            education: resume.education || '',
            source: 'library'
          });
        }
      }
    } catch (error) {
      console.warn('Error reading library resumes:', error);
    }
  }

  if (allResumes.length === 0) {
    alert('Could not extract text from any of the selected resumes.');
    scanButton.disabled = false;
    scanButton.innerHTML = '<span>Scan Resumes</span>';
    if (scanSelectedBtn) {
      scanSelectedBtn.disabled = false;
    }
    return;
  }

  const payload = {
    jobDescription: jobText,
    resumes: allResumes
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
      const sourceResume = allResumes.find(u => u.name === r.name) || allResumes[i] || {};
      return {
        ...r,
        email: r.email || sourceResume.email || '',
        phone: r.phone || sourceResume.phone || '',
        linkedin: r.linkedin || sourceResume.linkedin || '',
        location: r.location || sourceResume.location || '',
        currentRole: r.currentRole || sourceResume.currentRole || r.title || '',
        currentCompany: r.currentCompany || sourceResume.currentCompany || '',
        education: r.education || sourceResume.education || '',
        experience: r.experience || sourceResume.experience || 0
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
    if (scanSelectedBtn) {
      scanSelectedBtn.disabled = false;
    }
  }
}

// Scan selected library resumes combined with uploaded files
async function scanSelectedResumes() {
  const jobText = jobDescription.value;

  if (!jobText.trim()) {
    alert('Please enter a job description first.');
    return;
  }

  if (selectedResumeIds.size === 0) {
    alert('Please select resumes from the library to scan.');
    return;
  }

  // Run analysis including library resumes
  await runAnalysis(true);
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
scanButton.addEventListener('click', () => runAnalysis(true));

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
  refreshFileList(Array.from(event.target.files), true);
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
  refreshFileList(Array.from(event.dataTransfer.files), true);
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
const modalTitle = document.getElementById('modalTitle');
const resumeContent = document.getElementById('resumeContent');
const closeModal = document.getElementById('closeModal');

let selectedResumeIds = new Set();

// Storage constants
const MAX_STORAGE_MB = 100;
const storageBar = document.getElementById('storageBar');
const storageUsed = document.getElementById('storageUsed');
const storagePercent = document.getElementById('storagePercent');

function updateLibraryCount(count) {
  if (libraryCount) {
    libraryCount.textContent = count;
  }
}

function calculateStorageSize(resumes) {
  // Calculate total size of all resume content in bytes
  let totalBytes = 0;
  resumes.forEach(resume => {
    const content = resume.content || resume.resume || '';
    // Estimate size: each character is roughly 1 byte for ASCII, 2-3 for Unicode
    totalBytes += new Blob([content]).size;
    // Add metadata size estimate
    totalBytes += JSON.stringify({
      name: resume.name,
      email: resume.email,
      phone: resume.phone,
      location: resume.location,
      education: resume.education,
      currentRole: resume.currentRole
    }).length;
  });
  return totalBytes;
}

function updateStorageIndicator(resumes) {
  const totalBytes = calculateStorageSize(resumes);
  const totalMB = totalBytes / (1024 * 1024);
  const percentage = Math.min(100, (totalMB / MAX_STORAGE_MB) * 100);

  if (storageUsed) {
    storageUsed.textContent = totalMB.toFixed(2) + ' MB';
  }

  if (storageBar) {
    storageBar.style.width = percentage + '%';
    // Change color based on usage
    if (percentage >= 90) {
      storageBar.className = 'progress-bar storage-critical';
    } else if (percentage >= 70) {
      storageBar.className = 'progress-bar storage-warning';
    } else {
      storageBar.className = 'progress-bar storage-ok';
    }
  }

  if (storagePercent) {
    storagePercent.textContent = Math.round(percentage) + '%';
    // Update chip color
    if (percentage >= 90) {
      storagePercent.className = 'score-chip critical';
    } else if (percentage >= 70) {
      storagePercent.className = 'score-chip warning';
    } else {
      storagePercent.className = 'score-chip ok';
    }
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
    updateStorageIndicator(resumes);
    selectedResumeIds.clear();

    if (resumes.length === 0) {
      libraryGrid.innerHTML = '<div class="empty-state">No resumes in library. Upload and save resumes to build your library.</div>';
      updateStorageIndicator([]);
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

  if (uploadFiles.length > MAX_UPLOAD_LIMIT) {
    alert(`Too many resumes selected. Maximum ${MAX_UPLOAD_LIMIT} allowed per upload.`);
    return;
  }

  saveResumesBtn.disabled = true;
  saveResumesBtn.innerHTML = '<span>Saving...</span>';

  try {
    for (const file of uploadFiles) {
      // Use PDF extraction for PDF files, text() for others
      const text = await extractTextFromFile(file);

      if (!text || text.trim().length === 0) {
        console.warn(`Could not extract text from ${file.name}`);
        continue;
      }

      const contactInfo = extractContactInfo(text);
      const roleInfo = extractCurrentRole(text);
      const candidateName = extractCandidateName(text, file.name);

      await saveResumeToLibrary({
        name: candidateName,
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

if (scanSelectedBtn) {
  scanSelectedBtn.addEventListener('click', scanSelectedResumes);
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
