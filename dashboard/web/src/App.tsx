import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './layout/AppLayout'
import { AlertsPage } from './pages/AlertsPage'
import { EpisodesPage } from './pages/EpisodesPage'
import { MapPage } from './pages/MapPage'
import { OlapPage } from './pages/OlapPage'
import { OverviewPage } from './pages/OverviewPage'
import { PredictionsPage } from './pages/PredictionsPage'
import { ReplayPage } from './pages/ReplayPage'
import { StationsPage } from './pages/StationsPage'
import { WeatherPage } from './pages/WeatherPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/tram" element={<StationsPage />} />
          <Route path="/dot-o-nhiem" element={<EpisodesPage />} />
          <Route path="/thoi-tiet" element={<WeatherPage />} />
          <Route path="/du-bao" element={<PredictionsPage />} />
          <Route path="/canh-bao" element={<AlertsPage />} />
          <Route path="/phat-lai" element={<ReplayPage />} />
          <Route path="/olap" element={<OlapPage />} />
          <Route path="/ban-do" element={<MapPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
