import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Bell, Building2, Check, ChevronDown, Command, Settings, UserRound } from 'lucide-react'
import type { LauncherDomain, LauncherModule, TopMenuItem } from '../types'
import { Button } from './ui/button'

type HeaderProps = {
  collapsedLeft: boolean
  collapsedRight: boolean
  domains: LauncherDomain[]
  activeDomainId: string
  activeModule?: LauncherModule
  topMenus: TopMenuItem[]
  activeTopMenuId: string
  onToggleLeft: () => void
  onToggleRight: () => void
  onSelectDomain: (domainId: string) => void
  onSelectTopMenu: (menuId: string) => void
}

export function Header({
  collapsedLeft,
  collapsedRight,
  domains,
  activeDomainId,
  activeModule,
  topMenus,
  activeTopMenuId,
  onToggleLeft,
  onToggleRight,
  onSelectDomain,
  onSelectTopMenu,
}: HeaderProps) {
  const activeDomain = domains.find((domain) => domain.domainId === activeDomainId)

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">
          <Building2 size={24} />
        </div>
        <div>
          <strong>DevBank</strong>
          <span>Enterprise AI Launcher</span>
        </div>
      </div>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <Button variant="outline" className="domain-trigger">
            <span>Dominio</span>
            <strong>{activeDomain?.label ?? 'Todos'}</strong>
            <ChevronDown size={15} />
          </Button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="dropdown-content" align="start" sideOffset={8}>
            <DropdownMenu.Item className="dropdown-item" onSelect={() => onSelectDomain('all')}>
              <span>Todos</span>
              {activeDomainId === 'all' && <Check size={15} />}
            </DropdownMenu.Item>
            {domains.map((domain) => (
              <DropdownMenu.Item className="dropdown-item" key={domain.domainId} onSelect={() => onSelectDomain(domain.domainId)}>
                <span>{domain.label}</span>
                {activeDomainId === domain.domainId && <Check size={15} />}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <nav className="top-menu" aria-label="Menu del modulo activo">
        <span className="top-menu-module">{activeModule?.label ?? 'Home'}</span>
        {topMenus.slice(0, 5).map((menu) => (
          <button
            className={`top-menu-item ${activeTopMenuId === menu.id ? 'active' : ''}`}
            key={menu.id}
            type="button"
            onClick={() => onSelectTopMenu(menu.id)}
          >
            {menu.label}
          </button>
        ))}
      </nav>

      <div className="topbar-actions">
        <Button variant="outline" size="sm" onClick={onToggleLeft}>
          <Command size={16} />
          {collapsedLeft ? 'Abrir nav' : 'Nav'}
        </Button>
        <Button variant="outline" size="sm" onClick={onToggleRight}>
          <Command size={16} />
          {collapsedRight ? 'Abrir detalle' : 'Detalle'}
        </Button>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button variant="ghost" size="icon" aria-label="Notificaciones">
              <Bell size={18} />
              <span className="notification-dot">3</span>
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className="dropdown-content notification-menu" align="end" sideOffset={8}>
              <DropdownMenu.Label className="dropdown-label">Notificaciones</DropdownMenu.Label>
              <DropdownMenu.Item className="dropdown-item">3 flows pendientes de revision</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item">Registry actualizado</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item">AskService activo</DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button variant="ghost" size="sm">
              <UserRound size={18} />
              Saul
              <ChevronDown size={14} />
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className="dropdown-content" align="end" sideOffset={8}>
              <DropdownMenu.Label className="dropdown-label">Perfil</DropdownMenu.Label>
              <DropdownMenu.Item className="dropdown-item">Mi cuenta</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item">Preferencias</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item">Sesiones</DropdownMenu.Item>
              <DropdownMenu.Separator className="dropdown-separator" />
              <DropdownMenu.Item className="dropdown-item">Cerrar sesion</DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button variant="ghost" size="icon" aria-label="Settings">
              <Settings size={18} />
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className="dropdown-content" align="end" sideOffset={8}>
              <DropdownMenu.Label className="dropdown-label">Settings</DropdownMenu.Label>
              <DropdownMenu.Item className="dropdown-item">Apariencia</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item">Roles y permisos</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item">Registro de modulos</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item">Integraciones</DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  )
}
