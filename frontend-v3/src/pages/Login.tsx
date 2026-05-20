import { useState } from 'react';
import { APP_CONFIG } from '@/config/app';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
import { ThemeToggle } from '@/components/theme/ThemeToggle';
import logosPrefeitura from '@/assets/logos-prefeitura-transparent.png';
import logoGitly from '@/assets/logo-gitly.png';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (login(username, password)) {
      navigate('/');
    } else {
      setError('Credenciais inválidas. Tente novamente.');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-primary relative overflow-hidden p-4">
      <div className="absolute top-4 right-4 z-20">
        <ThemeToggle className="text-primary-foreground hover:bg-primary-foreground/15" />
      </div>
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <motion.div
          className="absolute -top-20 -right-20 w-96 h-96 rounded-full opacity-10"
          style={{ background: 'hsl(var(--secondary))' }}
          animate={{ scale: [1, 1.2, 1], rotate: [0, 90, 0] }}
          transition={{ duration: 20, repeat: Infinity }}
        />
        <motion.div
          className="absolute -bottom-32 -left-32 w-[500px] h-[500px] rounded-full opacity-5"
          style={{ background: 'hsl(var(--secondary))' }}
          animate={{ scale: [1.2, 1, 1.2], rotate: [0, -90, 0] }}
          transition={{ duration: 25, repeat: Infinity }}
        />
        {/* Rain drops */}
        {Array.from({ length: 30 }).map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-0.5 h-4 rounded-full bg-primary-foreground/10"
            style={{ left: `${Math.random() * 100}%`, top: -20 }}
            animate={{ y: ['0vh', '110vh'] }}
            transition={{
              duration: 1.5 + Math.random() * 2,
              repeat: Infinity,
              delay: Math.random() * 3,
              ease: 'linear',
            }}
          />
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-md relative z-10"
      >
        <Card className="border border-border/60 shadow-2xl backdrop-blur-sm bg-card text-card-foreground">
          <CardHeader className="text-center pb-2 pt-8">
            <div className="flex flex-col items-center gap-4 mb-4">
              <div className="rounded-lg p-3 transition-colors dark:border dark:border-secondary/35 dark:bg-white/[0.92] dark:shadow-[0_0_0_1px_hsl(var(--secondary)/0.12),0_10px_28px_hsl(var(--secondary)/0.10)]">
                <img src={logosPrefeitura} alt="Prefeitura de Santo André, CAF e Defesa Civil" className="h-40 w-auto object-contain" />
              </div>
              <img src={logoGitly} alt="Gitly" className="h-8 w-auto object-contain" />
            </div>
            <h1 className="text-2xl font-heading font-bold text-primary">
              Defesa Civil
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Sistema de Predição de Alagamentos e Inundações
            </p>
            <p className="text-xs text-muted-foreground/70 mt-1">
              Santo André
            </p>
          </CardHeader>
          <CardContent className="pt-4 pb-8 px-8">
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-foreground font-medium">
                  Usuário
                </Label>
                <Input
                  id="username"
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="Digite seu usuário"
                  required
                  className="h-11"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-foreground font-medium">
                  Senha
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Digite sua senha"
                  required
                  className="h-11"
                />
              </div>
              {error && (
                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center gap-2 text-destructive text-sm"
                >
                  <AlertTriangle className="h-4 w-4" />
                  {error}
                </motion.div>
              )}
              <Button
                type="submit"
                className="w-full h-11 text-base font-semibold bg-secondary text-secondary-foreground hover:bg-secondary/90"
              >
                Entrar
              </Button>
            </form>
          </CardContent>
        </Card>
        <p className="text-center text-primary-foreground/40 text-xs mt-6">
          v{APP_CONFIG.APP_VERSION} — Sistema de Predição de Alagamentos
        </p>
      </motion.div>
    </div>
  );
}
