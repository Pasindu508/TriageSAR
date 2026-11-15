import { Link } from 'react-router-dom';
import { useDocumentTitle } from '../accessibility/useDocumentTitle';
import { ErrorNote, Loading } from '../components/Status';
import { useMethodology } from '../hooks/queries';

export function MethodologyPage() {
  useDocumentTitle('Methodology');
  const { data, isLoading, isError, error } = useMethodology();
  return (
    <div className="page">
      <p className="eyebrow">Methodology</p>
      <h1>How the science works</h1>
      <p className="lede">
        Every step is deterministic and every threshold is in one configuration file. There is no machine
        learning and no language model anywhere in the ranking.
      </p>
      {isLoading ? <Loading what="the methodology" /> : null}
      {isError ? <ErrorNote error={error} context="the methodology" /> : null}
      {data ? (
        <>
          <h2>Pipeline</h2>
          <ol>
            {data.pipeline.map((p) => (
              <li key={p.step}>
                <strong style={{ color: 'var(--text)' }}>{p.step.replace(/^\d+\.\s*/, '')}.</strong>{' '}
                {p.detail}
              </li>
            ))}
          </ol>

          <h2>From phase to line-of-sight range change</h2>
          <p className="equation">{data.equation}</p>
          <p style={{ marginTop: 10 }}>{data.sign_convention}</p>
          <p>{data.sign_convention_basis}</p>

          <h2>Quality states</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">State</th>
                  <th scope="col">Meaning</th>
                  <th scope="col">Map encoding</th>
                </tr>
              </thead>
              <tbody>
                {data.quality_states.map((s) => (
                  <tr key={s.state}>
                    <th scope="row" style={{ color: 'var(--text)' }}>
                      {s.state}
                    </th>
                    <td>{s.meaning}</td>
                    <td>{s.encoding}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Quality rules</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Rule</th>
                  <th scope="col">Result</th>
                  <th scope="col">Rationale</th>
                </tr>
              </thead>
              <tbody>
                {data.quality_rules.map((r) => (
                  <tr key={r.rule}>
                    <td className="mono">{r.rule}</td>
                    <td>{r.result}</td>
                    <td>{r.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Deformation zones</h2>
          <p>{data.threshold_rule}</p>

          <h2>Inspection priority score</h2>
          <p className="equation">{data.score_formula}</p>
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Factor</th>
                  <th scope="col" className="num">
                    Weight
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.score_components.map((c) => (
                  <tr key={c.name}>
                    <td>{c.label}</td>
                    <td className="num">{c.weight.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ marginTop: 10 }}>{data.sensitivity}</p>

          <h2>Corrections</h2>
          <p>{data.corrections}</p>

          <h2>What is not claimed</h2>
          <ul>
            {data.not_claimed.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <p style={{ marginTop: 16 }}>
            See also the <Link to="/limitations">limitations</Link>.
          </p>
        </>
      ) : null}
    </div>
  );
}
