import type { EvidenceQuality } from '../types/api';
import { AlertIcon, CheckIcon, SlashIcon } from './Icons';

const TEXT: Record<EvidenceQuality, { label: string; title: string; cls: string }> = {
  VALID: {
    label: 'VALID',
    title: 'Most radar pixels along this road pass every quality rule',
    cls: 'chip-valid',
  },
  CAUTION: {
    label: 'CAUTION',
    title: 'Radar evidence along this road is usable but weaker',
    cls: 'chip-caution',
  },
  INSUFFICIENT: {
    label: 'INSUFFICIENT',
    title: 'Too few usable radar pixels along this road to characterise motion',
    cls: 'chip-insufficient',
  },
};

/** Quality is encoded three ways: icon shape, border style and a text label (never colour alone). */
export function QualityChip({ quality }: { quality: EvidenceQuality }) {
  const t = TEXT[quality];
  return (
    <span className={`chip ${t.cls}`} title={t.title}>
      {quality === 'VALID' ? <CheckIcon /> : quality === 'CAUTION' ? <AlertIcon /> : <SlashIcon />}
      <span>
        <span className="sr-only">Evidence quality: </span>
        {t.label}
      </span>
    </span>
  );
}

/** Label for a share of VALID pixels, used for zones (same cut-offs as road corridors). */
export function zoneQuality(valid: number, caution: number): EvidenceQuality {
  if (valid >= 0.75) return 'VALID';
  if (valid + caution >= 0.5) return 'CAUTION';
  return 'INSUFFICIENT';
}
