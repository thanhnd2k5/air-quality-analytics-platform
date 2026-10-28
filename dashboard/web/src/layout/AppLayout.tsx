import { AppShell, Burger, Group, NavLink, Stack, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconAlertTriangle,
  IconChartLine,
  IconCube,
  IconCloud,
  IconMap2,
  IconHome,
  IconCircles,
  IconBuildingFactory2,
} from '@tabler/icons-react'
import type { ComponentType } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

type NavItem = {
  to: string
  label: string
  icon: ComponentType<{ size?: number; stroke?: number }>
}

type NavSection = {
  id: string
  label: string
  hint: string
  items: NavItem[]
}

const SECTIONS: NavSection[] = [
  {
    id: 'warehouse',
    label: 'Kho dữ liệu',
    hint: 'Câu hỏi theo thời gian, địa điểm và hướng gió',
    items: [
      { to: '/', label: 'Tổng quan', icon: IconHome },
      { to: '/olap', label: 'Phân tích OLAP', icon: IconCube },
    ],
  },
  {
    id: 'mining',
    label: 'Khai phá dữ liệu',
    hint: 'Giờ tới có vượt ngưỡng 115 µg/m³ hay không',
    items: [
      { to: '/canh-bao', label: 'Cảnh báo', icon: IconAlertTriangle },
    ],
  },
  {
    id: 'support',
    label: 'Phân tích bổ trợ',
    hint: 'Phân cụm, trạm, khí tượng và hồi quy',
    items: [
      { to: '/phan-cum', label: 'Phân cụm', icon: IconCircles },
      { to: '/tram', label: 'Trạm', icon: IconBuildingFactory2 },
      { to: '/ban-do', label: 'Bản đồ', icon: IconMap2 },
      { to: '/thoi-tiet', label: 'Thời tiết', icon: IconCloud },
      { to: '/du-bao', label: 'Dự báo giá trị', icon: IconChartLine },
    ],
  },
]

function sectionFor(pathname: string) {
  return SECTIONS.find((section) => section.items.some((item) => item.to === pathname)) ?? SECTIONS[0]
}

export function AppLayout() {
  const [opened, { toggle }] = useDisclosure()
  const location = useLocation()
  const section = sectionFor(location.pathname)

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 248,
        breakpoint: 'sm',
        collapsed: { mobile: !opened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4}>Chất lượng không khí Bắc Kinh</Title>
          </Group>
          <Stack gap={0} align="flex-end" visibleFrom="sm">
            <Text size="sm" fw={600}>
              {section.label}
            </Text>
            <Text size="xs" c="dimmed">
              {section.hint}
            </Text>
          </Stack>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm" style={{ overflowY: 'auto' }}>
        <Stack gap="md">
          {SECTIONS.map((group) => (
            <Stack key={group.id} gap={2}>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="sm" pt={4}>
                {group.label}
              </Text>
              {group.items.map((item) => (
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
            </Stack>
          ))}
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
