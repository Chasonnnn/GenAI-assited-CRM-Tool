/**
 * MSW Server for Node.js (Vitest) environment
 * 
 * This server intercepts HTTP requests during tests.
 */

import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
