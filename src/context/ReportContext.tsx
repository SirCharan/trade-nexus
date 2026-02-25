import { createContext, useContext, useReducer, type ReactNode } from 'react'
import type { ReportData } from '../types/report'

interface AppState {
  report: ReportData | null;
  activeTab: number;
  loading: boolean;
  error: string | null;
  fileName: string | null;
}

type Action =
  | { type: 'SET_LOADING' }
  | { type: 'SET_REPORT'; payload: ReportData; fileName: string }
  | { type: 'SET_ERROR'; payload: string }
  | { type: 'SET_TAB'; payload: number }
  | { type: 'CLEAR' };

const initialState: AppState = {
  report: null,
  activeTab: 0,
  loading: false,
  error: null,
  fileName: null,
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, loading: true, error: null };
    case 'SET_REPORT':
      return { ...state, report: action.payload, fileName: action.fileName, loading: false, error: null };
    case 'SET_ERROR':
      return { ...state, loading: false, error: action.payload };
    case 'SET_TAB':
      return { ...state, activeTab: action.payload };
    case 'CLEAR':
      return initialState;
    default:
      return state;
  }
}

const ReportContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<Action>;
} | null>(null);

export function ReportProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <ReportContext.Provider value={{ state, dispatch }}>
      {children}
    </ReportContext.Provider>
  );
}

export function useReport() {
  const ctx = useContext(ReportContext);
  if (!ctx) throw new Error('useReport must be used within ReportProvider');
  return ctx;
}
