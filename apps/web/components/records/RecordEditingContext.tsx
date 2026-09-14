"use client"

import { createContext, useContext } from "react"

export const RecordEditingContext = createContext(true)
export const useRecordEditing = () => useContext(RecordEditingContext)
