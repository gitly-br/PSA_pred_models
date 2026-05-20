import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import {
  BarChart3,
  Building2,
  ExternalLink,
  FileText,
  HelpCircle,
  Home,
  Landmark,
  LayoutPanelLeft,
  LogOut,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { APP_CONFIG } from '@/config/app';
import { ThemeToggle } from '@/components/theme/ThemeToggle';
import logosPrefeitura from '@/assets/logos-prefeitura-transparent.png';

const navItems = [
  { to: '/', label: 'Home', icon: Home },
  { to: '/chamados', label: 'Chamados', icon: LayoutPanelLeft },
];

const supportLinks = [
  {
    type: 'internal',
    to: '/modelos-detalhados',
    label: 'Detalhes dos Modelos',
    icon: BarChart3,
  },
  {
    type: 'external',
    href: 'https://docs.google.com/forms/d/e/1FAIpQLSe5lRV6Bx-VmKay4eBvWoiOqbS5qX2p3eKKeMYU7Di3SJTYIg/viewform?pli=1',
    label: 'Formulário solicitação',
    icon: FileText,
  },
  {
    type: 'external',
    href: 'https://gitly.notion.site/Ajuda-PSA-Dashboard-185ad90ac24c802b80faee77754fb4cf?pvs=4',
    label: 'Ajuda',
    icon: HelpCircle,
  },
  {
    type: 'external',
    href: 'https://portais.santoandre.sp.gov.br/defesacivil/',
    label: 'Defesa Civil',
    icon: ShieldAlert,
  },
  {
    type: 'external',
    href: 'https://portais.santoandre.sp.gov.br/defesacivil/centro-de-resiliencia/',
    label: 'Centro de Resiliência',
    icon: Building2,
  },
  {
    type: 'external',
    href: 'https://www.caf.com/pt/',
    label: 'CAF',
    icon: Landmark,
  },
] as const;

export default function AppSidebar({ className }: { className?: string }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside
      className={cn(
        'flex flex-col h-full border-r border-sidebar-border bg-sidebar text-sidebar-foreground',
        className,
      )}
    >
      {/* Logo area */}
      <div className="p-4 border-b border-sidebar-border flex flex-col items-center">
        <div className="w-full max-w-[212px] rounded-lg p-2 transition-colors dark:border dark:border-secondary/35 dark:bg-white/[0.92] dark:shadow-[0_0_0_1px_hsl(var(--secondary)/0.12),0_10px_28px_hsl(var(--secondary)/0.10)]">
          <img
            src={logosPrefeitura}
            alt="Prefeitura de Santo André, CAF e Defesa Civil"
            className="w-full h-auto object-contain"
          />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
              isActive
                ? 'bg-secondary text-secondary-foreground shadow-sm'
                : 'text-sidebar-foreground/70 hover:bg-sidebar-border/50 hover:text-sidebar-foreground'
            )}
          >
            <item.icon className="h-4 w-4 flex-shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Info section */}
      <div className="p-4 border-t border-sidebar-border">
        <div className="space-y-1.5">
          <p className="px-2 text-[10px] font-semibold uppercase tracking-wide text-sidebar-muted">
            Links úteis
          </p>
          {supportLinks.map(link => {
            const Icon = link.icon;

            if (link.type === 'internal') {
              return (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) => cn(
                    'flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium transition-colors',
                    isActive
                      ? 'bg-sidebar-border/70 text-sidebar-foreground'
                      : 'text-sidebar-muted hover:bg-sidebar-border/50 hover:text-sidebar-foreground',
                  )}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  <span className="min-w-0 flex-1 truncate">{link.label}</span>
                </NavLink>
              );
            }

            return (
              <a
                key={link.href}
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium text-sidebar-muted transition-colors hover:bg-sidebar-border/50 hover:text-sidebar-foreground"
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{link.label}</span>
                <ExternalLink className="h-3 w-3 shrink-0 opacity-60" />
              </a>
            );
          })}
        </div>
      </div>

      {/* User / Logout */}
      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-sidebar-foreground truncate">{user?.username}</p>
            <p className="text-xs text-sidebar-muted">v{APP_CONFIG.APP_VERSION}</p>
          </div>
          <ThemeToggle className="text-sidebar-foreground hover:bg-sidebar-border/60" />
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="text-sidebar-muted hover:text-destructive shrink-0"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
