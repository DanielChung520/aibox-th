import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';
import logoDark from '../assets/EDGE-logo-icon.png';
import logoLight from '../assets/EDGE-logo-dark.png';

export default function Home() {
  const contentTokens = useContentTokens();
  const effectiveTheme = useEffectiveTheme();
  const logoSrc = effectiveTheme === 'dark' ? logoDark : logoLight;

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      {logoSrc ? (
        <img
          src={logoSrc}
          alt="logo"
          style={{
            width: 400,
            height: 400,
            objectFit: 'contain',
          }}
        />
      ) : (
        <div style={{
          width: 400,
          height: 400,
          background: `linear-gradient(135deg, ${contentTokens.colorPrimary} 0%, ${contentTokens.colorInfo} 100%)`,
          borderRadius: 24,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 128,
          color: contentTokens.btnText,
          fontWeight: 'bold',
        }}>
          ABC
        </div>
      )}
    </div>
  );
}
