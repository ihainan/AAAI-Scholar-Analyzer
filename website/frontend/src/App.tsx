import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ConferenceList from './pages/ConferenceList';
import ConferenceDetail from './pages/ConferenceDetail';
import ScholarDetail from './pages/ScholarDetail';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ConferenceList />} />
        <Route path="/conference/:conferenceId" element={<ConferenceDetail />} />
        <Route path="/conference/:conferenceId/scholar" element={<ScholarDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
