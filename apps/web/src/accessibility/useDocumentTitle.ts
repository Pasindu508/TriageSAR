import { useEffect } from 'react';

/** Sets the document title so screen-reader users hear which view they are on. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = title ? `${title} · TriageSAR` : 'TriageSAR';
  }, [title]);
}
