import { AppShell, Burger, Group, NavLink, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconChartLine,
  IconCloud,
  IconMap2,
  IconRadar2,
  IconHome,
  IconBuildingFactory2,
} from '@tabler/icons-react'
import { Link, Outlet, useLocation } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Tổng quan', icon: IconHome },
  { to: '/tram', label: 'Trạm', icon: IconBuildingFactory2 },
  { to: '/dot-o-nhiem', label: 'Đợt ô nhiễm', icon: IconRadar2 },
  { to: '/thoi-tiet', label: 'Thời tiết', icon: IconCloud },
  { to: '/du-bao', label: 'Dự báo', icon: IconChartLine },
  { to: '/ban-do', label: 'Bản đồ', icon: IconMap2 },
] as const

export function AppLayout() {
  const [opened, { toggle }] = useDisclosure()
  const location = useLocation()

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 240,
        breakpoint: 'sm',
        collapsed: { mobile: !opened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4}>Chất lượng không khí Bắc Kinh</Title>
          </Group>
          <Text size="sm" c="dimmed">
            Dashboard đọc DWH / marts
          </Text>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={item.label}
            leftSection={<item.icon size={18} stroke={1.5} />}
            active={location.pathname === item.to}
            onClick={() => {
              if (opened) toggle()
            }}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
