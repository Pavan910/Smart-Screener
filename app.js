const sampleJobDescription = `Senior Data Analyst with strong business communication, SQL, Python, dashboard design, stakeholder management, and experience translating source data into measurable insights for executive decision-making.`;

const sampleCandidates = [
  {
    name: 'Olivia Johnson',
    title: 'Senior Data Analyst',
    experience: 7,
    email: 'olivia.johnson@example.com',
    skills: ['python', 'sql', 'dashboard', 'stakeholder', 'business communication'],
    resume: 'Olivia Johnson is a Senior Data Analyst with 7 years of experience in Python, SQL, business intelligence dashboards, and stakeholder communication. Built executive reports for product and supply chain teams and translated data into growth insights. Strong experience with data storytelling, KPI design, and dashboard design.'
  },
  {
    name: 'Harper Lee',
    title: 'Business Intelligence Lead',
    experience: 6,
    email: 'harper.lee@example.com',
    skills: ['sql', 'dashboard', 'stakeholder', 'business communication'],
    resume: 'Harper Lee brings 6 years of analytics experience in dashboard design and SQL analytics. Strong communication with business stakeholders and experience delivering weekly dashboards for leadership. Skilled in sales insights, KPI frameworks, and business performance analysis.'
  },
  {
    name: 'Sophia Brown',
    title: 'Analytics Manager',
    experience: 5,
    email: 'sophia.brown@example.com',
    skills: ['sql', 'dashboard', 'business communication'],
    resume: 'Sophia Brown has 5 years of analytics experience with dashboard delivery and business data storytelling. Comfortable in SQL reporting and working with operations teams. Experience with business commitment, cross-functional product reporting, and stakeholder reviews.'
  },
  {
    name: 'Evelyn Smith',
    title: 'Data Science Specialist',
    experience: 4,
    email: 'evelyn.smith@example.com',
    skills: ['python', 'machine learning', 'sql'],
    resume: 'Evelyn Smith has 4 years of work in Python, data science, classification, and SQL modeling. Experience working with customer data pipelines and forecasting. Has strong technical background but less emphasis on stakeholder communication and executive dashboard design.'
  }
];

const skillLibrary = {
  python: { synonyms: ['python', 'pandas', 'numpy', 'scikit-learn', 'jupyter'] },
  sql: { synonyms: ['sql', 'postgres', 'mysql', 'database', 'query'] },
  dashboard: { synonyms: ['dashboard', 'tableau', 'power bi', 'bi', 'reporting'] },
  business: { synonyms: ['business communication', 'business stakeholder', 'stakeholder management', 'communication', 'executive'] },
  analytics: { synonyms: ['analytics', 'data analysis', 'kpi', 'insights'] }
};

const jobDescription = document.getElementById('jobDescription');
const scanButton = document.getElementById('scanButton');
const sampleButton = document.getElementById('sampleButton');
const loadJobButton = document.getElementById('loadJobButton');
const resumeFiles = document.getElementById('resumeFiles');
const dropZone = document.getElementById('dropZone');
const fileList = document.getElementById('fileList');
const uploadStatus = document.getElementById('uploadStatus');
const rankingList = document.getElementById('rankingList');
const resultsTable = document.getElementById('resultsTable');
const clearFiles = document.getElementById('clearFiles');
const bestCandidateCard = document.getElementById('bestCandidateCard');

function normalizeText(text) {
  return text.toLowerCase().replace(/[^a-z0-9\s\-]/g, ' ');
}

function extractSkillKeywords(text) {
  const normalized = normalizeText(text);
  const skills = [];

  Object.entries(skillLibrary).forEach(([key, value]) => {
    const found = value.synonyms.some(s => normalized.includes(s));
    if (found) {
      skills.push(key);
    }
  });

  return skills;
}

function scoreCandidate(candidate, jobText) {
  const normalizedCandidate = normalizeText(candidate.resume);
  const normalizedJob = normalizeText(jobText);

  const skillKeywords = extractSkillKeywords(jobText);
  const coveredSkills = skillKeywords.filter(skill => {
    const synonyms = skillLibrary[skill].synonyms;
    return synonyms.some(s => normalizedCandidate.includes(s));
  });

  const skillScore = Math.round((coveredSkills.length / Math.max(skillKeywords.length, 1)) * 60);

  const expScore = Math.min(14, Math.max(candidate.experience - 2, 0) * 2);
  const keywordFrequency = Math.min(16, Math.max(0, countKeywordMatches(normalizedCandidate, normalizedJob)));

  const base = skillScore + expScore + keywordFrequency;
  const fit = Math.min(96, Math.max(55, Math.round(base)));

  return {
    name: candidate.name,
    title: candidate.title,
    experience: candidate.experience,
    score: fit,
    coveredSkills,
    missingSkills: skillKeywords.filter(s => !coveredSkills.includes(s)),
    text: candidate.resume,
    email: candidate.email
  };
}

function countKeywordMatches(candidateText, jobText) {
  const jobWords = new Set(jobText.replace(/[^a-z0-9\s]/g, '').split(/\s+/).filter(Boolean));
  let total = 0;

  jobWords.forEach(word => {
    if (word.length < 3) return;
    if (candidateText.includes(word)) total += 1;
  });

  return total;
}

function renderRankings(ranking) {
  const sorted = ranking.sort((a, b) => b.score - a.score);

  rankingList.innerHTML = '';
  resultsTable.innerHTML = '';

  sorted.slice(0, 5).forEach((item, index) => {
    const row = document.createElement('div');
    row.className = 'rank-row';

    const barWidth = Math.min(100, Math.max(30, item.score));

    row.innerHTML = `
      <span class="rank-name">${item.name}</span>
      <span class="rank-bar-wrap"><span class="rank-bar ${index === 0 ? 'rank-high' : 'rank-mid'}" style="width:${barWidth}%;"></span></span>
      <span class="rank-score">${item.score}</span>
    `;

    rankingList.appendChild(row);
  });

  sorted.forEach((item, index) => {
    const tr = document.createElement('tr');

    const fitClass = item.score >= 88 ? 'tag-fit' : item.score >= 75 ? 'tag-fit mid' : 'tag-fit low';
    const decision = item.score >= 88 ? 'Shortlist' : item.score >= 75 ? 'Review' : 'Pool';
    const decisionClass = item.score >= 88 ? 'decision-shortlist' : item.score >= 75 ? 'decision-review' : 'decision-pool';

    tr.innerHTML = `
      <td class="rank-token">${String(index + 1).padStart(2, '0')}</td>
      <td>
        <span class="table-name">${item.name}</span>
        <span class="table-subtitle">${item.title}</span>
      </td>
      <td><span class="tag ${fitClass}">${item.score >= 88 ? 'Very High' : item.score >= 75 ? 'High' : 'Medium'}</span></td>
      <td><span class="score-number">${item.score}</span></td>
      <td>${item.experience} years</td>
      <td><span class="decision ${decisionClass}">${decision}</span></td>
    `;

    resultsTable.appendChild(tr);
  });
}

function renderBestCandidate(ranking) {
  const sorted = [...ranking].sort((a, b) => b.score - a.score);
  const top = sorted[0];

  bestCandidateCard.innerHTML = `
    <div class="candidate-head">
      <div>
        <span class="candidate-avatar">${getInitials(top.name)}</span>
      </div>
      <div>
        <span class="candidate-name">${top.name}</span>
        <span class="candidate-title">${top.title}</span>
      </div>
      <span class="candidate-score">${top.score}</span>
    </div>
    <div class="candidate-body">
      <div class="candidate-details">
        <div>
          <span class="candidate-label">Experience</span>
          <span class="candidate-value">${top.experience} years</span>
        </div>
        <div>
          <span class="candidate-label">Skill Match</span>
          <span class="candidate-value">${top.coveredSkills.map(capitalize).join(', ') || 'None'}</span>
        </div>
      </div>
      <div class="candidate-readiness">
        <span class="readiness-title">Fit Summary</span>
        <span class="readiness-text">${top.score >= 88 ? 'Strong skills alignment with business communication, analytics, and reporting depth.' : 'Below expected coverage on key role requirements. Needs review.'}</span>
      </div>
    </div>
  `;
}

function updateDashboardMetrics(ranking) {
  const sorted = [...ranking].sort((a, b) => b.score - a.score);
  const top = sorted[0];

  const coverageScore = Math.round((top.coveredSkills.length / Math.max(extractSkillKeywords(jobDescription.value).length, 1)) * 100);
  const total = ranking.length;
  const shortlisted = ranking.filter(item => item.score >= 88).length;

  document.getElementById('metricScanned').textContent = String(total).padStart(2, '0');
  document.getElementById('metricTopScore').textContent = String(top.score);
  document.getElementById('metricCoverage').textContent = String(Math.min(100, coverageScore)) + '%';
  document.getElementById('metricShortlist').textContent = String(shortlisted).padStart(2, '0');
}

function getInitials(name) {
  return name.split(' ').map(n => n.slice(0, 1)).slice(0, 2).join('');
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function buildCandidateFromFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (event) => {
      const text = event.target.result || file.name;
      const candidate = {
        name: file.name.replace(/\.[^/.]+$/, '').split(/[_-]/).map(capitalize).join(' '),
        title: 'Resume Upload',
        experience: 4,
        email: 'resume@uploaded.com',
        skills: [],
        resume: text
      };

      resolve(candidate);
    };

    reader.onerror = () => reject(new Error('Could not read file'));

    if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
      resolve({
        name: file.name,
        title: 'PDF Resume',
        experience: 4,
        email: 'resume@uploaded.com',
        skills: [],
        resume: 'PDF resume extracted summary unavailable. Use a text file or PDF text import service for a stronger parse.'
      });
    } else {
      reader.readAsText(file);
    }
  });
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
  const jobText = jobDescription.value || sampleJobDescription;
  const uploadFiles = Array.from(resumeFiles.files);

  const uploadedResumes = [];

  if (uploadFiles.length > 0) {
    try {
      uploadedResumes.push(...await Promise.all(uploadFiles.map(async file => {
        const text = await file.text();
        return {
          name: file.name,
          title: 'Uploaded Resume',
          resume: text || file.name
        };
      })));
    } catch (error) {
      console.warn('Unable to read uploaded files as text:', error);
    }
  }

  const payload = {
    jobDescription: jobText,
    resumes: uploadedResumes
  };

  try {
    const response = await fetch('/api/rank', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Ranking API returned ${response.status}`);
    }

    const result = await response.json();
    const ranking = Array.isArray(result.ranking) ? result.ranking : [];

    if (ranking.length > 0) {
      renderRankings(ranking);
      renderBestCandidate(ranking);
      updateDashboardMetrics(ranking);
    } else {
      runRanking(sampleCandidates, jobText);
    }
  } catch (error) {
    console.error(error);
    runRanking(sampleCandidates, jobText);
  }
}

function runRanking(candidates, jobText) {
  const ranking = candidates.map(candidate => scoreCandidate(candidate, jobText));
  renderRankings(ranking);
  renderBestCandidate(ranking);
  updateDashboardMetrics(ranking);
}

scanButton.addEventListener('click', runAnalysis);
sampleButton.addEventListener('click', () => {
  const sample = sampleCandidates[0].resume;
  jobDescription.value = sampleJobDescription;
  runRanking(sampleCandidates, sampleJobDescription);
});

loadJobButton.addEventListener('click', () => {
  jobDescription.value = sampleJobDescription;
});

clearFiles.addEventListener('click', () => {
  resumeFiles.value = '';
  refreshFileList([]);
});

resumeFiles.addEventListener('change', event => {
  refreshFileList(Array.from(event.target.files));
});

// Drag and drop support
let draggedFiles = [];
dropZone.addEventListener('dragover', event => {
  event.preventDefault();
  dropZone.style.borderColor = '#246b68';
});

dropZone.addEventListener('drop', event => {
  event.preventDefault();
  dropZone.style.borderColor = '#dae7e8';

  const files = Array.from(event.dataTransfer.files);
  draggedFiles = files;

  // Preserve same file input object by creating a DataTransfer
  resumeFiles.files = event.dataTransfer.files;
  refreshFileList(files);
});

runRanking(sampleCandidates, sampleJobDescription);
