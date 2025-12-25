import { useAuth } from '@/contexts/AuthContext'

/**
 * Hook to check if the current user is an admin.
 * Returns true if the user is logged in and has admin privileges.
 */
export function useIsAdmin(): boolean {
  const { user } = useAuth()
  return user?.is_admin === true
}

