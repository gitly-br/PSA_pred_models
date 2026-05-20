import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import AppSidebar from './AppSidebar';
import { Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/theme/ThemeToggle';
import { cn } from '@/lib/utils';
import logoGitly from '@/assets/logo-gitly.png';

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden lg:block w-64 flex-shrink-0">
        <AppSidebar />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-foreground/30 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div className={cn(
        'fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-300 ease-in-out lg:hidden',
        mobileOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <AppSidebar />
        <Button
          variant="ghost"
          size="icon"
          className="absolute top-3 right-3 text-sidebar-foreground"
          onClick={() => setMobileOpen(false)}
        >
          <X className="h-5 w-5" />
        </Button>
      </div>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {/* Mobile header */}
        <div className="lg:hidden flex items-center gap-3 p-4 border-b border-border bg-card sticky top-0 z-30">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>
          <h1 className="font-heading font-bold text-primary text-sm flex-1 min-w-0 truncate">
            Defesa Civil — Santo André
          </h1>
          <ThemeToggle className="shrink-0" />
        </div>

        <div className="min-h-full p-4 md:p-6 lg:p-8">
          <Outlet />
          <footer className="mt-10 flex items-center justify-center gap-2 border-t border-border/70 pt-4 text-xs text-muted-foreground">
            <span>Desenvolvido por</span>
            <img src={logoGitly} alt="Gitly" className="h-4 w-auto object-contain opacity-75" />
          </footer>
        </div>
      </main>
    </div>
  );
}
