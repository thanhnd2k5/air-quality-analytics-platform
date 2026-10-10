import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './layout/AppLayout'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { StationsPage } from './pages/StationsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route
            path="/"
            element={
              <PlaceholderPage
                title="Tổng quan"
                note="KPI và xu hướng PM2.5 sẽ nối mart_station_daily / monthly (P11b)."
              />
            }
          />
          <Route path="/tram" element={<StationsPage />} />
          <Route
            path="/dot-o-nhiem"
            element={<PlaceholderPage title="Đợt ô nhiễm" />}
          />
          <Route
            path="/thoi-tiet"
            element={<PlaceholderPage title="Thời tiết" />}
          />
          <Route path="/du-bao" element={<PlaceholderPage title="Dự báo" />} />
          <Route path="/ban-do" element={<PlaceholderPage title="Bản đồ" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
