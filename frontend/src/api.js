// All requests go to our own backend. No API keys ever live in the frontend.
async function handle(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail)
      ? "Check your input: the CV needs 200–15,000 characters and the job description 100–10,000."
      : data.detail;
    throw new Error(detail || `Request failed (${res.status}).`);
  }
  return data;
}

export async function extractPdf(file) {
  const form = new FormData();
  form.append("file", file);
  return handle(await fetch("/api/extract", { method: "POST", body: form }));
}

export async function tailor(cvText, jobText) {
  return handle(
    await fetch("/api/tailor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cv_text: cvText, job_text: jobText }),
    })
  );
}
