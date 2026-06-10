import { useState } from 'react';
import { Upload, BarChart3, AlertTriangle, CheckCircle, Search, Server } from 'lucide-react';
import api from './api/client';

// Views
import UploadView from './components/Upload/UploadView';
import FilterView from './components/Filters/FilterView';
import DashboardView from './components/Dashboard/DashboardView';

function App() {
  const [step, setStep] = useState(1);
  const [uploadData, setUploadData] = useState(null);
  const [selections, setSelections] = useState({ proyecto: '', fecha: '' });
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Handlers
  const handleFileUpload = async (file) => {
    setIsLoading(true);
    try {
      const resp = await api.uploadBaseExcel(file);
      setUploadData(resp);
      setStep(2);
    } catch (error) {
      alert("Error al cargar el archivo: " + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectionSubmit = async (proyecto, fecha) => {
    setSelections({ proyecto, fecha });
    setIsLoading(true);
    try {
      const reportData = await api.runValidation(proyecto, fecha);
      setReport(reportData);
      setStep(3);
    } catch (error) {
      alert("Error al ejecutar validaciones: " + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setStep(1);
    setUploadData(null);
    setSelections({ proyecto: '', fecha: '' });
    setReport(null);
  };

  return (
    <div className="app-container">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-brand">
          <ActivityIcon color="var(--accent-color)" size={24} />
          <span>CashFlow Auditor <span style={{color: 'var(--text-secondary)', fontWeight: 400}}>| Real Estate</span></span>
        </div>
        
        {step > 1 && (
          <button className="btn btn-secondary" onClick={handleReset} style={{fontSize: '0.75rem', padding: '0.25rem 0.5rem'}}>
            Comenzar de nuevo
          </button>
        )}
      </header>

      {/* Main Content */}
      <main className="main-content">
        {step === 1 && (
          <UploadView onUpload={handleFileUpload} isLoading={isLoading} />
        )}
        
        {step === 2 && uploadData && (
          <FilterView 
            data={uploadData} 
            onSubmit={handleSelectionSubmit} 
            onBack={() => setStep(1)}
            isLoading={isLoading} 
          />
        )}

        {step === 3 && report && (
          <DashboardView 
            report={report} 
            selections={selections}
            onBack={() => setStep(2)} 
          />
        )}
      </main>
    </div>
  );
}

// Icon helper
const ActivityIcon = ({color, size}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
  </svg>
);

export default App;
