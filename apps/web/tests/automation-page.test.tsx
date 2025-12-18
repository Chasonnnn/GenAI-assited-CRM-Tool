import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import AutomationPage from '../app/(app)/automation/page'

describe('AutomationPage', () => {
    it('renders', () => {
        render(<AutomationPage />)
        expect(screen.getByText('Automation')).toBeInTheDocument()
    })
})

