interface JobQuestion {
  question?: string;
  answer?: string;
  field_type?: string;
  options?: string[];
}

interface JobRecord {
  job_id: number;
  session_id: number;
  linkedin_job_id: number;
  title: string;
  description?: string;
  status: string;
  created_at?: string;
  questions_answers: JobQuestion[];
}


let jobs: JobRecord[] = [];
const statusFilter = document.getElementById("statusFilter") as HTMLSelectElement;
const searchFilter = document.getElementById("searchFilter") as HTMLInputElement;
const metricsContainer = document.getElementById("metrics") as HTMLDivElement;
const summaryContainer = document.getElementById("summary") as HTMLDivElement;
const jobListContainer = document.getElementById("jobList") as HTMLDivElement;

function formatValue(value: string | undefined): string {
  if (!value) return "—";
  return value;
}

const sessionFilter =
    document.getElementById("sessionFilter") as HTMLSelectElement;

async function loadSessions(): Promise<void> {

    const response = await fetch("/api/sessions");

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    const sessions = await response.json();

    sessionFilter.innerHTML =
        `<option value="">All Sessions</option>` +
        sessions.map((s: any) => `
            <option value="${s.id}">
                Session ${s.id} (${s.total_jobs} jobs)
            </option>
        `).join("");

    sessionFilter.value = "";

    await loadJobs();
}

async function loadJobs(sessionId?: number): Promise<void> {
    try {
        const url = sessionId
            ? `/api/jobs/${sessionId}`
            : "/api/jobs";

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        jobs = await response.json();

        renderDashboard();
    } catch (error) {
        console.error("Failed to load jobs:", error);

        metricsContainer.innerHTML =
            "<div class='card'>Unable to load jobs.</div>";

        summaryContainer.innerHTML = "";

        jobListContainer.innerHTML =
            "<div class='card'>Check that the backend is running.</div>";
    }
}


function populateStatusFilter(): void {
    const current = statusFilter.value;

    const statuses = [
        "All",
        ...new Set(jobs.map(job => job.status))
    ];

    statusFilter.innerHTML = statuses
        .map(status => `<option value="${status}">${status}</option>`)
        .join("");

    if (statuses.includes(current)) {
        statusFilter.value = current;
    }
}

function renderDashboard(): void {

  populateStatusFilter();

  const filteredJobs = jobs.filter((job) => {
    const matchesStatus = statusFilter.value === "All" || job.status === statusFilter.value;
    const query = searchFilter.value.trim().toLowerCase();
    const matchesQuery =
      !query ||
      job.title.toLowerCase().includes(query) ||
      job.questions_answers.some((question) => (question.question ?? "").toLowerCase().includes(query));
    return matchesStatus && matchesQuery;
  });

  const statusCounts = filteredJobs.reduce<Record<string, number>>((counts, job) => {
    counts[job.status] = (counts[job.status] ?? 0) + 1;
    return counts;
  }, {});

  metricsContainer.innerHTML = [
    `<div class="metric"><span>Total applications</span><strong>${filteredJobs.length}</strong></div>`,
    ...Object.entries(statusCounts).map(([status, count]) => `<div class="metric"><span>${status}</span><strong>${count}</strong></div>`),
    `<div class="metric"><span>Captured questions</span><strong>${filteredJobs.reduce((total, job) => total + job.questions_answers.length, 0)}</strong></div>`,
  ].join("");

  summaryContainer.innerHTML = `<strong>Showing ${filteredJobs.length} of ${jobs.length} applications</strong>`;

  jobListContainer.innerHTML = filteredJobs.length
    ? filteredJobs
        .map(
          (job) => `
            <article class="card job-item">
              <h3>${job.title} <span class="tag">${job.status}</span></h3>
              <p><strong>Job ID:</strong> ${job.job_id}</p>
              <p><strong>LinkedIn ID:</strong> ${job.linkedin_job_id}</p>
              <p><strong>Created:</strong> ${formatValue(job.created_at)}</p>
              <p>${job.description ?? "No description provided."}</p>
              ${job.questions_answers.length ? `<ul>${job.questions_answers.map((question) => `<li><strong>${question.question ?? "Question"}</strong>: ${question.answer ?? "No answer"}</li>`).join("")}</ul>` : "<p>No captured questions.</p>"}
            </article>
          `,
        )
        .join("")
    : '<div class="card">No matching applications found.</div>';
}

statusFilter.addEventListener("change", renderDashboard);
searchFilter.addEventListener("input", renderDashboard);
sessionFilter.addEventListener("change", async () => {

    if (sessionFilter.value === "") {
        await loadJobs();
    } else {
        await loadJobs(Number(sessionFilter.value));
    }

});
loadSessions();