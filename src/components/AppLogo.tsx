import { useNavigate } from 'react-router-dom';
import logoFull from '../assets/EDGE-logo-light.png';
import logoIcon from '../assets/EDGE-logo-icon.png';

interface AppLogoProps {
  logo: string;
  collapsed: boolean;
  textColor: string;
  borderColor: string;
}

export default function AppLogo({ logo, collapsed }: AppLogoProps) {
  const navigate = useNavigate();
  const src = (logo && logo.length > 0) ? logo : undefined;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        height: '100%',
        cursor: 'pointer',
      }}
      onClick={() => navigate('/app/home')}
    >
      <img
        src={src ?? (collapsed ? logoIcon : logoFull)}
        alt="EDGE logo"
        style={{
          height: collapsed ? 32 : 28,
          width: 'auto',
          objectFit: 'contain',
          display: 'block',
        }}
      />
    </div>
  );
}
