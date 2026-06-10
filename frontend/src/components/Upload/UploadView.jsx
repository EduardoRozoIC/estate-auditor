import { useState, useCallback } from 'react';
import { Upload, FileBox, AlertCircle } from 'lucide-react';

export default function UploadView({ onUpload, isLoading }) {
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState('');

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const processFile = (file) => {
    setError('');
    if (!file) return;
    if (!file.name.match(/\.(xlsx|xls)$/)) {
      setError('Por favor sube únicamente un archivo Excel (.xlsx, .xls)');
      return;
    }
    onUpload(file);
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  return (
    <div style={{maxWidth: '600px', margin: '4rem auto'}}>
      <div style={{marginBottom: '2rem', textAlign: 'center'}}>
        <h1 style={{fontSize: '2rem', marginBottom: '0.5rem'}}>Carga de Datos BASE</h1>
        <p style={{color: 'var(--text-secondary)'}}>
          Sube el archivo Excel con el flujo histórico versionado para iniciar la validación.
        </p>
      </div>

      <div 
        className={`drop-zone ${dragActive ? 'active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        {isLoading ? (
          <div style={{padding: '2rem'}}>
            <Upload className="drop-zone-icon" size={48} style={{animation: 'bounce 1s infinite'}} />
            <h3>Procesando archivo...</h3>
            <p style={{color: 'var(--text-secondary)', marginTop: '0.5rem'}}>
              Leyendo estructura y construyendo diccionario de proyectos.
            </p>
          </div>
        ) : (
          <>
            <FileBox className="drop-zone-icon" size={48} />
            <h3 style={{marginBottom: '0.5rem'}}>Arrastra el Excel aquí</h3>
            <p style={{color: 'var(--text-secondary)', marginBottom: '1.5rem'}}>o haz clic para seleccionar (solo hojas completas)</p>
            <input 
              type="file" 
              accept=".xlsx,.xls" 
              onChange={handleChange}
              style={{display: 'none'}} 
              id="file-input" 
            />
            <label htmlFor="file-input" className="btn btn-primary">
              <Upload size={16} /> Seleccionar Archivo
            </label>
          </>
        )}
      </div>

      {error && (
        <div style={{marginTop: '1.5rem', padding: '1rem', backgroundColor: 'var(--bg-critical)', border: '1px solid var(--color-critical)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)'}}>
          <AlertCircle color="var(--color-critical)" size={20} />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
