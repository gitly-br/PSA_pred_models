import { Navigate } from 'react-router-dom';

/** Rota legada — redireciona para a página unificada de Chamados. */
export default function OccurrenceMapPage() {
  return <Navigate to="/chamados" replace />;
}
