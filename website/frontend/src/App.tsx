import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ConferenceList from './pages/ConferenceList';
import ConferenceDetail from './pages/ConferenceDetail';
import ScholarDetail from './pages/ScholarDetail';
import AuthorDetail from './pages/AuthorDetail';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ConferenceList />} />
        <Route path="/conference/:conferenceId" element={<ConferenceDetail />} />
        <Route path="/conference/:conferenceId/scholar" element={<ScholarDetail />} />
        <Route path="/conference/:conferenceId/author/:authorName" element={<AuthorDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
