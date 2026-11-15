import { useEffect, useRef } from 'react';
import { useProvenance } from '../hooks/queries';
import { shortHash, utcDateTime } from '../lib/format';
import type { ProvenanceEvent } from '../types/api';
import { ErrorNote, Loading } from './Status';

function EventProvenance({ ev }: { ev: ProvenanceEvent }) {
  const m = ev.fixture_manifest;
  const osm = ev.infrastructure_manifest;
  const granule = ev.event_definition.granule;
  return (
    <section className="section" aria-labelledby={`prov-${ev.event_id}`}>
      <h3
        id={`prov-${ev.event_id}`}
        style={{ fontSize: '1rem', textTransform: 'none', letterSpacing: 0, color: 'var(--text)' }}
      >
        {ev.event_definition.title}
      </h3>
      {ev.data_kind === 'synthetic_test' ? (
        <p className="note">Synthetic test data. Not NASA observations.</p>
      ) : null}
      {!m ? (
        <div className="note">
          <strong>Real-data fixture not built on this machine.</strong> No NISAR values are shown for this
          event.
          {granule ? (
            <dl className="kv" style={{ marginTop: 8 }}>
              <dt>Granule found</dt>
              <dd className="mono">{granule.granule_id}</dd>
              <dt>Collection</dt>
              <dd>{granule.collection}</dd>
              <dt>Found with</dt>
              <dd className="mono">{granule.discovered_with}</dd>
              <dt>Found on</dt>
              <dd>{granule.discovered_on} (ASF Search API)</dd>
            </dl>
          ) : null}
        </div>
      ) : (
        <>
          <h4 className="eyebrow" style={{ margin: '12px 0 6px' }}>
            NISAR source product
          </h4>
          <dl className="kv">
            <dt>Granule</dt>
            <dd className="mono">{m.source.granule_id}</dd>
            <dt>Collection</dt>
            <dd>
              {m.source.collection ?? 'not recorded'} {m.source.concept_id ? `(${m.source.concept_id})` : ''}
            </dd>
            <dt>Provider</dt>
            <dd>{m.source.provider ?? 'not recorded'}</dd>
            <dt>Reference</dt>
            <dd>{utcDateTime(m.acquisition.reference_start_utc)}</dd>
            <dt>Secondary</dt>
            <dd>{utcDateTime(m.acquisition.secondary_start_utc)}</dd>
            <dt>Track / frame</dt>
            <dd>
              {m.source.track_number ?? '–'} / {m.source.frame_number ?? '–'} ·{' '}
              {m.source.orbit_pass_direction ?? '–'}
            </dd>
            <dt>Product version</dt>
            <dd>{m.source.product_version ?? 'not recorded'}</dd>
            <dt>Processor</dt>
            <dd>{m.source.software_version ?? 'not recorded'}</dd>
            <dt>Wavelength</dt>
            <dd>
              {m.radar.wavelength_m.toFixed(6)} m ({m.radar.derivation.replace('_', ' ')}) from{' '}
              <span className="mono">{m.radar.source_hdf5_path}</span>
            </dd>
          </dl>
          <h4 className="eyebrow" style={{ margin: '16px 0 6px' }}>
            Fixture
          </h4>
          <dl className="kv">
            <dt>Crop window</dt>
            <dd>
              rows {m.aoi.row_start}–{m.aoi.row_stop}, columns {m.aoi.col_start}–{m.aoi.col_stop} of{' '}
              {m.aoi.source_height} × {m.aoi.source_width}
            </dd>
            <dt>Bounding box</dt>
            <dd className="mono">{m.aoi.bbox_wgs84_requested.join(', ')}</dd>
            <dt>Grid</dt>
            <dd>
              {m.grid.width} × {m.grid.height} px, EPSG:{m.grid.epsg ?? '–'}
            </dd>
            <dt>Built</dt>
            <dd>
              {utcDateTime(m.build.built_at_utc)} · app {m.build.app_version}
            </dd>
            <dt>Command</dt>
            <dd className="mono">{m.build.command}</dd>
            <dt>Checksums</dt>
            <dd>
              {ev.checksum_problems && ev.checksum_problems.length === 0
                ? 'All layer files match their recorded SHA-256.'
                : (ev.checksum_problems ?? []).join('; ')}
            </dd>
          </dl>
          <div className="table-wrap" style={{ marginTop: 10 }}>
            <table className="data">
              <caption className="sr-only">Fixture layers with source paths and checksums</caption>
              <thead>
                <tr>
                  <th scope="col">Layer</th>
                  <th scope="col">Source HDF5 path</th>
                  <th scope="col">SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(m.layers).map(([name, layer]) => (
                  <tr key={name}>
                    <td>
                      {name}
                      <br />
                      <span className="scale-note">{layer.dtype}</span>
                    </td>
                    <td className="mono" style={{ overflowWrap: 'anywhere' }}>
                      {layer.hdf5_path}
                    </td>
                    <td className="mono" title={layer.sha256}>
                      {shortHash(layer.sha256)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h4 className="eyebrow" style={{ margin: '16px 0 6px' }}>
            Transformations and corrections
          </h4>
          <ul className="plain">
            {m.transformations.map((t) => (
              <li key={t}>{t}</li>
            ))}
            <li>{m.corrections.statement}</li>
            <li>
              Correction layers shipped with the product and left untouched:{' '}
              {m.corrections.available_layers.length}.
            </li>
          </ul>
        </>
      )}
      {osm ? (
        <>
          <h4 className="eyebrow" style={{ margin: '16px 0 6px' }}>
            Roads
          </h4>
          <dl className="kv">
            <dt>Source</dt>
            <dd>{osm.provider}</dd>
            <dt>Licence</dt>
            <dd>
              <a href={osm.licence_url} target="_blank" rel="noreferrer">
                {osm.licence}
              </a>{' '}
              · {osm.attribution}
            </dd>
            <dt>OSM data as of</dt>
            <dd>{utcDateTime(osm.osm_base_timestamp)}</dd>
            <dt>Features</dt>
            <dd>
              {osm.files['roads.geojson']?.features ?? 0} road ways,{' '}
              {osm.files['places.geojson']?.features ?? 0} place labels
            </dd>
            <dt>Command</dt>
            <dd className="mono">{osm.command}</dd>
          </dl>
        </>
      ) : null}
      {ev.event_definition.event_source_url ? (
        <p className="scale-note" style={{ marginTop: 12 }}>
          Event information:{' '}
          <a href={ev.event_definition.event_source_url} target="_blank" rel="noreferrer">
            {ev.event_definition.event_source_name}
          </a>
        </p>
      ) : null}
    </section>
  );
}

export function ProvenanceDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const provenance = useProvenance(open);
  useEffect(() => {
    const node = dialog.current;
    if (!node) return;
    if (open && !node.open) node.showModal();
    if (!open && node.open) node.close();
  }, [open]);
  return (
    <dialog ref={dialog} className="drawer" aria-labelledby="prov-title" onClose={onClose}>
      <div className="drawer-head">
        <h2 id="prov-title">Provenance</h2>
        <button type="button" className="btn btn-small" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="drawer-body">
        {provenance.isLoading ? <Loading what="provenance" /> : null}
        {provenance.isError ? <ErrorNote error={provenance.error} context="provenance" /> : null}
        {provenance.data ? (
          <>
            <p className="note info">{provenance.data.application.statement}</p>
            <dl className="kv" style={{ marginTop: 12 }}>
              <dt>Application</dt>
              <dd>
                {provenance.data.application.name} {provenance.data.application.version} ·{' '}
                {provenance.data.application.licence}
              </dd>
              <dt>Schema version</dt>
              <dd>{provenance.data.schema_version}</dd>
            </dl>
            {provenance.data.events.map((ev) => (
              <EventProvenance key={ev.event_id} ev={ev} />
            ))}
          </>
        ) : null}
      </div>
    </dialog>
  );
}
