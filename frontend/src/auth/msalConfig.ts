import { Configuration, LogLevel } from '@azure/msal-browser'

const CLIENT_ID = import.meta.env.VITE_CLIENT_ID as string
const TENANT_ID = import.meta.env.VITE_TENANT_ID as string

export const msalConfig: Configuration = {
  auth: {
    clientId: CLIENT_ID,
    authority: `https://login.microsoftonline.com/${TENANT_ID}`,
    redirectUri: `${window.location.origin}/auth/callback`,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return
        if (level === LogLevel.Error) console.error('[MSAL]', message)
      },
      logLevel: LogLevel.Error,
    },
  },
}

/** Scopes for the ID token — openid + profile is enough for login */
export const loginRequest = {
  scopes: ['openid', 'profile', 'User.Read'],
}
