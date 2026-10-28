import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './layout/AppLayout'
import { AlertsPage } from './pages/AlertsPage'
import { ClustersPage } from './pages/ClustersPage'
import { MapPage } from './pages/MapPage'
import { OlapPage } from './pages/OlapPage'
import { OverviewPage } from './pages/OverviewPage'
import { PredictionsPage } from './pages/PredictionsPage'
import { QualityPage } from './pages/QualityPage'
import { WeatherPage } from './pages/WeatherPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/phan-cum" element={<ClustersPage />} />
          <Route path="/thoi-tiet" element={<WeatherPage />} />
          <Route path="/du-bao" element={<PredictionsPage />} />
          <Route path="/canh-bao" element={<AlertsPage />} />
          <Route path="/olap" element={<OlapPage />} />
          <Route path="/chat-luong" element={<QualityPage />} />
          <Route path="/ban-do" element={<MapPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
