import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { CommandCenter } from './pages/CommandCenter';
import { OrchestratorProvider } from './contexts/OrchestratorContext';
import './index.css';

function App() {
  return (
    <OrchestratorProvider>
      <Router>
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          {/* C-OS Primarily uses the unified CommandCenter view */}
          <Route path="*" element={<CommandCenter />} />
        </Routes>
      </Router>
    </OrchestratorProvider>
  );
}

export default App;
