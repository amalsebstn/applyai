import { useState } from "react";
import { extractPdf, tailor } from "./api.js";

// Security note (OWASP LLM05): every piece of model output below is rendered as
// plain React text. We never use dangerouslySetInnerHTML, so a model reply
// containing <script> or HTML is displayed as harmless text.

export default function App() {
  const [cv, setCv] = useState("");
  const [job, setJob] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  async function onPdf(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const { text } = await extractPdf(file);
      setCv(text);
    } catch (err) {
      setError(err.message);
    }
    e.target.value = "";
  }

  async function onSubmit() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await tailor(cv, job));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyLetter() {
    await navigator.clipboard.writeText(result.cover_letter);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  const ready = cv.trim().length >= 200 && job.trim().length >= 100;

  return (
    <div className="page">
      <header className="masthead">
        <h1>ApplyAI</h1>
        <p>Tailor your CV to a job without inventing anything. Claims the model adds that aren't in your CV get marked for you to check.</p>
      </header>

      <main className="layout">
        <section className="inputs" aria-label="Your documents">
          <div className="field">
            <div className="field-head">
              <label htmlFor="cv">Your CV</label>
              <label className="upload">
                Upload PDF
                <input type="file" accept="application/pdf" onChange={onPdf} />
              </label>
            </div>
            <textarea id="cv" value={cv} onChange={(e) => setCv(e.target.value)}
              placeholder="Paste your CV text, or upload a PDF." maxLength={15000} />
            <span className="count">{cv.length.toLocaleString()} / 15,000</span>
          </div>

          <div className="field">
            <label htmlFor="job">Job description</label>
            <textarea id="job" value={job} onChange={(e) => setJob(e.target.value)}
              placeholder="Paste the full job description." maxLength={10000} />
            <span className="count">{job.length.toLocaleString()} / 10,000</span>
          </div>

          <button className="primary" onClick={onSubmit} disabled={!ready || busy}>
            {busy ? "Tailoring…" : "Tailor my CV"}
          </button>
          <p className="privacy">Your email, phone number and profile links are removed before anything is sent to the AI. Nothing is stored.</p>
        </section>

        <section className="results" aria-live="polite" aria-label="Results">
          {error && <p className="error" role="alert">{error}</p>}

          {!result && !error && (
            <div className="empty">
              <p>Paste your CV and a job description, then select Tailor my CV.</p>
              <p>You'll get a match score, your gaps, rewritten bullets and a short cover letter.</p>
            </div>
          )}

          {result && (
            <>
              {result.injection_warnings.length > 0 && (
                <p className="warning">
                  The job description contains text that looks like instructions to an AI
                  ({result.injection_warnings.join(", ")}). It was treated as data and ignored, but review the results carefully.
                </p>
              )}

              <div className="score">
                <span className="score-num">{result.match_score}</span>
                <span className="score-label">match with this job</span>
              </div>

              <div className="two-col">
                <div>
                  <h2>Strengths</h2>
                  <ul>{result.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
                <div>
                  <h2>Gaps</h2>
                  <ul>{result.gaps.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              </div>

              {result.missing_keywords.length > 0 && (
                <>
                  <h2>Keywords missing from your CV</h2>
                  <p className="keywords">{result.missing_keywords.join(", ")}</p>
                </>
              )}

              <h2>Tailored bullets</h2>
              <ul className="bullets">
                {result.bullets.map((b, i) => (
                  <li key={i} className={b.unverified_terms.length ? "flagged" : ""}>
                    <span className="bullet-text"><span className="hl">{b.text}</span></span>
                    {b.unverified_terms.length > 0 && (
                      <span className="margin-note">
                        Not in your CV: {b.unverified_terms.join(", ")}. Remove or rewrite unless it's true.
                      </span>
                    )}
                  </li>
                ))}
              </ul>

              <div className="letter-head">
                <h2>Cover letter draft</h2>
                <button className="secondary" onClick={copyLetter}>{copied ? "Copied" : "Copy letter"}</button>
              </div>
              <div className="letter">{result.cover_letter}</div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
