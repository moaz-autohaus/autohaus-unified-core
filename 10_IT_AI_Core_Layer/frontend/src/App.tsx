import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { CommandCenter } from './pages/CommandCenter';
import { InventoryMatrix } from './pages/InventoryMatrix';
import { SystemLedger } from './pages/SystemLedger';
import { BrainFeed } from './pages/BrainFeed';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<CommandCenter />} />
          <Route path="inventory" element={<InventoryMatrix />} />
          <Route path="ledger" element={<SystemLedger />} />
          <Route path="feed" element={<BrainFeed />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
