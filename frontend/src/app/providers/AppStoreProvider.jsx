import { AppStoreProvider as StoreAppStoreProvider } from '../../store/app/AppStore'

export function AppStoreProvider({ children }) {
  return <StoreAppStoreProvider>{children}</StoreAppStoreProvider>
}
