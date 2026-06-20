import * as Collapsible from '@radix-ui/react-collapsible'
import {
  BadgeDollarSign,
  Bot,
  ChevronDown,
  CircleUserRound,
  ChevronsLeft,
  ChevronsRight,
  CreditCard,
  Grid2X2,
  Home,
  LibraryBig,
  LockKeyhole,
  MessageSquare,
  Monitor,
  Puzzle,
  Settings,
  Sparkles,
  SquareCheckBig,
  Users,
  Workflow,
  Boxes,
} from 'lucide-react'
import type { LauncherModule } from '../types'
import { Button } from './ui/button'

const iconMap = {
  home: Home,
  loan: BadgeDollarSign,
  deposit: BadgeDollarSign,
  rates: LibraryBig,
  product: Puzzle,
  'credit-card': CreditCard,
  'deposit-account': BadgeDollarSign,
  'product-service-config': Puzzle,
  customer: Users,
  workflow: Workflow,
  admin: Settings,
  agents: Bot,
  skills: Sparkles,
  knowledge: LibraryBig,
  mcp: Puzzle,
  monitor: Monitor,
}

type LeftNavProps = {
  modules: LauncherModule[]
  activeModuleId: string
  collapsed: boolean
  onToggle: () => void
  onSelectModule: (module: LauncherModule) => void
  activeView: 'workspace' | 'assets' | 'skills'
  onSelectAssets: () => void
  onSelectSkills: () => void
  onOpenAgentDraft: () => void
}

export function LeftNav({
  modules,
  activeModuleId,
  collapsed,
  onToggle,
  onSelectModule,
  activeView,
  onSelectAssets,
  onSelectSkills,
  onOpenAgentDraft,
}: LeftNavProps) {
  const homeModule = modules.find((module) => module.module_id === 'home')
  const adminModule = modules.find((module) => module.module_id === 'admin')
  const businessModules = modules.filter((module) => !['home', 'admin'].includes(module.module_id))

  const generalItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Grid2X2, module: homeModule },
    { id: 'tasks', label: 'Tasks', icon: SquareCheckBig, module: homeModule },
    { id: 'apps', label: 'Apps', icon: Puzzle, module: homeModule },
    { id: 'skills', label: 'Skill', icon: Sparkles, module: undefined },
    { id: 'agents', label: 'Agents', icon: Bot, module: undefined },
    { id: 'chats', label: 'Chats', icon: MessageSquare, module: homeModule, badge: '3' },
    { id: 'users', label: 'Users', icon: Users, module: adminModule },
    { id: 'assets', label: 'Assets', icon: Boxes, module: undefined },
    { id: 'secured', label: 'Secured by Clerk', icon: LockKeyhole, module: adminModule, chevron: true },
  ]

  return (
    <aside className="sidebar left-sidebar">
      <div className="panel-title-row">
        {!collapsed && (
          <div className="sidebar-product">
            <div className="sidebar-product-mark">
              <Grid2X2 size={20} />
            </div>
            <div>
              <strong>Shadcn Admin</strong>
              <span>DevBank Launcher</span>
            </div>
          </div>
        )}
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Colapsar navegacion">
          {collapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}
        </Button>
      </div>

      <nav className="nav-list">
        {!collapsed && <p className="nav-section-label">General</p>}
        {generalItems.map((item) => {
          const Icon = item.icon
          const active =
            item.id === 'assets'
              ? activeView === 'assets'
              : item.id === 'skills' || item.id === 'agents'
                ? activeView === 'skills'
              : activeView === 'workspace' && item.module?.module_id === activeModuleId && item.id === 'dashboard'
          return (
            <button
              className={`nav-item ${active ? 'active' : ''} ${collapsed ? 'icon-only' : ''}`}
              key={item.id}
              onClick={() => {
                if (item.id === 'assets') onSelectAssets()
                else if (item.id === 'skills') onSelectSkills()
                else if (item.id === 'agents') onOpenAgentDraft()
                else if (item.module) onSelectModule(item.module)
              }}
              type="button"
            >
              <Icon size={19} />
              {!collapsed && (
                <>
                  <span>{item.label}</span>
                  {item.badge && <span className="nav-badge">{item.badge}</span>}
                  {item.chevron && <ChevronDown className="nav-chevron" size={16} />}
                </>
              )}
            </button>
          )
        })}

        {!collapsed && <p className="nav-section-label">Modules</p>}
        {businessModules.map((module) => {
          const Icon = iconMap[module.module_id as keyof typeof iconMap] ?? iconMap[module.icon as keyof typeof iconMap] ?? Puzzle
          const active = module.module_id === activeModuleId
          return (
            <Collapsible.Root key={module.module_id} defaultOpen={active}>
              <button
                className={`nav-item ${active ? 'active' : ''} ${collapsed ? 'icon-only' : ''}`}
                onClick={() => onSelectModule(module)}
                type="button"
              >
                <Icon size={18} />
                {!collapsed && (
                  <>
                    <span>{module.label}</span>
                    {module.menus.length > 0 && (
                      <Collapsible.Trigger asChild>
                        <ChevronDown className="nav-chevron" size={16} />
                      </Collapsible.Trigger>
                    )}
                  </>
                )}
              </button>
              {!collapsed && module.menus.length > 0 && (
                <Collapsible.Content className="submenu">
                  {module.menus.map((item) => (
                    <button key={item.id} className="submenu-item" type="button" onClick={() => onSelectModule(module)}>
                      {item.label}
                    </button>
                  ))}
                </Collapsible.Content>
              )}
            </Collapsible.Root>
          )
        })}

        {!collapsed && <p className="nav-section-label">Other</p>}
        {adminModule && (
          <button
            className={`nav-item ${activeModuleId === 'admin' ? 'active' : ''} ${collapsed ? 'icon-only' : ''}`}
            onClick={() => onSelectModule(adminModule)}
            type="button"
          >
            <Settings size={19} />
            {!collapsed && <span>Admin</span>}
          </button>
        )}
      </nav>

      {!collapsed && (
        <div className="sidebar-user">
          <div className="sidebar-avatar">
            <CircleUserRound size={18} />
          </div>
          <div>
            <strong>satnaing</strong>
            <span>satnaingdev@gmail.com</span>
          </div>
          <ChevronDown size={16} />
        </div>
      )}
    </aside>
  )
}
