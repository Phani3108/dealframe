import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Upload } from './pages/Upload'
import { Results } from './pages/Results'
import { Observatory } from './pages/Observatory'
import { Intelligence } from './pages/Intelligence'
import { Finetuning } from './pages/Finetuning'
import { LocalPipeline } from './pages/LocalPipeline'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/results/:jobId" element={<Results />} />
          <Route path="/observatory" element={<Observatory />} />
          <Route path="/intelligence" element={<Intelligence />} />
          <Route path="/finetuning" element={<Finetuning />} />
          <Route path="/local" element={<LocalPipeline />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
