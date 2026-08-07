import { useMemo, useState } from "react";

export default function PatientPicker({ patients, selectedId, onSelect }) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients.slice(0, 40);
    return patients
      .filter((p) =>
        `${p.first_name} ${p.last_name}`.toLowerCase().includes(q)
      )
      .slice(0, 40);
  }, [patients, query]);

  const selected = patients.find((p) => p.id === selectedId);

  return (
    <div className="patient-picker">
      <label className="field-label" htmlFor="patient-search">
        Patient
      </label>
      <input
        id="patient-search"
        type="text"
        placeholder="Search by name..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="patient-search-input"
      />
      {selected && (
        <div className="selected-patient">
          <div className="selected-patient-name">
            {selected.first_name} {selected.last_name}
          </div>
          <div className="selected-patient-meta">
            {selected.gender} &middot; born {selected.birthdate} &middot;{" "}
            {selected.city}, {selected.state}
          </div>
        </div>
      )}
      <div className="patient-list">
        {filtered.map((p) => (
          <button
            key={p.id}
            className={`patient-list-item${p.id === selectedId ? " selected" : ""}`}
            onClick={() => onSelect(p.id)}
          >
            <span className="patient-name">
              {p.first_name} {p.last_name}
            </span>
            <span className="patient-meta">
              {p.gender} &middot; {p.birthdate}
            </span>
          </button>
        ))}
        {filtered.length === 0 && (
          <div className="patient-list-empty">No patients match &ldquo;{query}&rdquo;</div>
        )}
      </div>
    </div>
  );
}
