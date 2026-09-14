import { createContext, useContext, type AnchorHTMLAttributes } from 'react';
export const LocalNavigation = createContext<(tab: string) => void>(() => {});
export default function LocalLink(props: AnchorHTMLAttributes<HTMLAnchorElement>) {
  const navigate = useContext(LocalNavigation);
  return <a {...props} onClick={event => {
    props.onClick?.(event);
    if (!event.defaultPrevented && props.href?.startsWith('#')) {
      event.preventDefault();
      navigate(props.href.slice(1));
    }
  }} />;
}
