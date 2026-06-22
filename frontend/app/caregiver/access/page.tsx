import Link from "next/link";

type AccessPageProps = {
  searchParams?: Promise<{
    error?: string;
    next?: string;
  }>;
};

export default async function CaregiverAccessPage({ searchParams }: AccessPageProps) {
  const params = (await searchParams) ?? {};
  const nextPath = sanitizeNextPath(params.next);
  const errorMessage = errorCopy(params.error);

  return (
    <main className="access-shell">
      <section className="access-panel" aria-labelledby="caregiver-access-title">
        <p className="eyebrow">Caregiver access</p>
        <h1 id="caregiver-access-title">Review Space</h1>
        <p>
          Caregiver review includes alerts, wellness checks, action intelligence,
          actuation controls, and evidence history. Patient mode remains available
          separately for calm memory assistance.
        </p>
        {errorMessage ? (
          <div className="notice notice--bad" role="alert">
            <strong>{errorMessage.title}</strong>
            <p>{errorMessage.body}</p>
          </div>
        ) : null}
        <form className="access-form" method="post" action="/api/caregiver-access">
          <input type="hidden" name="next" value={nextPath} />
          <label htmlFor="passcode">Caregiver passcode</label>
          <input
            id="passcode"
            name="passcode"
            type="password"
            autoComplete="current-password"
            required
          />
          <button className="button" type="submit">
            Enter caregiver review
          </button>
        </form>
        <Link className="button button--secondary" href="/">
          Return to patient mode
        </Link>
      </section>
    </main>
  );
}

function sanitizeNextPath(value: string | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/api/")) {
    return "/caregiver";
  }
  return value;
}

function errorCopy(error: string | undefined): { title: string; body: string } | null {
  if (error === "invalid") {
    return {
      title: "Passcode not accepted",
      body: "Use the caregiver passcode configured for this deployment."
    };
  }
  if (error === "not_configured") {
    return {
      title: "Caregiver gate is not configured",
      body: "Set CAREGIVER_PASSCODE on the frontend deployment or disable CAREGIVER_ACCESS_ENABLED for local development."
    };
  }
  return null;
}
