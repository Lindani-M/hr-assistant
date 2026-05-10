import { Configuration, LogLevel } from '@azure/msal-browser'

const CLIENT_ID = 'c8ba4eb1-e66a-422d-8fc8-ec82c942825f'
const TENANT_ID = '046e8edd-a483-43f1-b6dc-bf3dff8cd6ee'

export const msalConfig: Configuration = {
  auth: {
    clientId: CLIENT_ID,
    authority: `https://login.microsoftonline.com/${TENANT_ID}`,
    redirectUri: `${window.location.origin}/auth/callback`,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
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
