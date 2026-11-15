import { Link } from 'react-router-dom';
import { useDocumentTitle } from '../accessibility/useDocumentTitle';

export function NotFoundPage() {
  useDocumentTitle('Page not found');
  return (
    <div className="page">
      <h1>Page not found</h1>
      <p>
        There is nothing at this address. <Link to="/">Go to the overview</Link>.
      </p>
    </div>
  );
}
