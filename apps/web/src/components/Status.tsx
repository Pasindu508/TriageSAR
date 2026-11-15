import { ApiError } from '../lib/api';

export function Loading({ what }: { what: string }) {
  return (
    <p className="loading" role="status">
      Loading {what}…
    </p>
  );
}

export function ErrorNote({ error, context }: { error: unknown; context: string }) {
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div className="note error" role="alert">
      <strong>Could not load {context}.</strong>{' '}
      {apiError ? apiError.message : 'An unexpected error occurred.'}
      {apiError?.hint ? <code className="cmd">{apiError.hint}</code> : null}
    </div>
  );
}
