import { Anchor, AppShell, Box, Burger, Group, NavLink, ScrollArea, Stack, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconAlertTriangle,
  IconChartLine,
  IconChevronRight,
  IconCircles,
  IconCloud,
  IconCube,
  IconDatabase,
  IconHome,
  IconMap2,
} from '@tabler/icons-react'
import { useEffect, type ComponentType } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { INK } from '../theme'

type NavItem = {
  to: string
  label: string
  icon: ComponentType<{ size?: number; stroke?: number; color?: string }>
  /** Reachable by URL (and named in the breadcrumb) but not listed in the sidebar. */
  hidden?: boolean
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
      { to: '/chat-luong', label: 'Chất lượng dữ liệu', icon: IconDatabase },
    ],
  },
  {
    id: 'mining',
    label: 'Khai phá dữ liệu',
    hint: 'Giờ tới có vượt ngưỡng 115 µg/m³ hay không',
    items: [{ to: '/canh-bao', label: 'Cảnh báo', icon: IconAlertTriangle }],
  },
  {
    id: 'support',
    label: 'Phân tích bổ trợ',
    hint: 'Phân cụm, bản đồ và khí tượng',
    items: [
      { to: '/phan-cum', label: 'Phân cụm', icon: IconCircles },
      { to: '/ban-do', label: 'Bản đồ', icon: IconMap2 },
      { to: '/thoi-tiet', label: 'Thời tiết', icon: IconCloud },
      // Regression is not one of the course's mining tasks; kept for the report, off the menu.
      { to: '/du-bao', label: 'Dự báo giá trị', icon: IconChartLine, hidden: true },
    ],
  },
]

function locate(pathname: string) {
  for (const section of SECTIONS) {
    const item = section.items.find((i) => i.to === pathname)
    if (item) return { section, item }
  }
  return { section: SECTIONS[0], item: SECTIONS[0].items[0] }
}

/** Monochrome mark: three particles of decreasing size (PM2.5). */
function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
      <circle cx="7" cy="14" r="5" fill={INK.primary} />
      <circle cx="15.5" cy="7.5" r="3.5" fill={INK.primary} opacity="0.7" />
      <circle cx="17.5" cy="16.5" r="2" fill={INK.primary} opacity="0.45" />
    </svg>
  )
}

const HEADER_H = 56

export function AppLayout() {
  const [opened, { toggle, close }] = useDisclosure()
  const location = useLocation()
  const { section, item } = locate(location.pathname)

  // New page: start at the top and hand focus to the content (screen readers announce it).
  useEffect(() => {
    window.scrollTo(0, 0)
    document.getElementById('main')?.focus({ preventScroll: true })
  }, [location.pathname])

  return (
    <AppShell
      layout="alt"
      header={{ height: HEADER_H }}
      navbar={{
        width: 248,
        breakpoint: 'sm',
        collapsed: { mobile: !opened },
      }}
      padding={0}
    >
      <a className="skip-link" href="#main">
        Bỏ qua đến nội dung
      </a>

      <AppShell.Header withBorder>
        <Group h="100%" px={{ base: 'md', sm: 'lg', lg: 'xl' }} justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Mở menu" />
            <Group gap={6} wrap="nowrap" component="nav" aria-label="Vị trí" style={{ minWidth: 0 }}>
              <Group gap={6} wrap="nowrap" visibleFrom="xs">
                <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                  {section.label}
                </Text>
                <IconChevronRight size={14} color="var(--mantine-color-gray-5)" aria-hidden />
              </Group>
              <Text size="sm" fw={600} truncate aria-current="page">
                {item.label}
              </Text>
            </Group>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar>
        <AppShell.Section h={HEADER_H} px="md" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Anchor component={Link} to="/" underline="never" c="dark" onClick={close} aria-label="Trang tổng quan">
              <Group gap={10} wrap="nowrap">
                <Mark />
                <Box lh={1.2}>
                  <Text fw={650} size="sm" lh={1.2}>
                    Không khí Bắc Kinh
                  </Text>
                  <Text size="xs" c="dimmed" lh={1.3}>
                    Kho dữ liệu & khai phá
                  </Text>
                </Box>
              </Group>
            </Anchor>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Đóng menu" />
          </Group>
        </AppShell.Section>

        <AppShell.Section grow component={ScrollArea} px="sm" py="md">
          <Stack gap="lg" component="nav" aria-label="Điều hướng chính">
            {SECTIONS.map((group) => (
              <Stack key={group.id} gap={2}>
                <Text size="xs" fw={500} c="dimmed" px="sm" pb={4} title={group.hint}>
                  {group.label}
                </Text>
                {group.items
                  .filter((nav) => !nav.hidden)
                  .map((nav) => {
                    const active = location.pathname === nav.to
                    return (
                      <NavLink
                        key={nav.to}
                        component={Link}
                        to={nav.to}
                        label={nav.label}
                        leftSection={
                          <nav.icon
                            size={18}
                            stroke={1.6}
                            color={active ? 'var(--mantine-color-brand-6)' : 'var(--mantine-color-gray-6)'}
                          />
                        }
                        active={active}
                        variant="subtle"
                        aria-current={active ? 'page' : undefined}
                        className="side-link"
                        onClick={close}
                      />
                    )
                  })}
              </Stack>
            ))}
          </Stack>
        </AppShell.Section>

      </AppShell.Navbar>

      <AppShell.Main>
        <Box id="main" tabIndex={-1} maw={1440} mx="auto" px={{ base: 'md', sm: 'lg', lg: 'xl' }} py="lg">
          <Outlet />
        </Box>
      </AppShell.Main>
    </AppShell>
  )
}
