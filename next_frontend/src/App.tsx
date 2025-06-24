import React, { useState, useEffect, useCallback } from 'react';
import PipelineVisual from './components/PipelineVisual';
import OutputPanel from './components/OutputPanel';
import ChatInterface from './components/ChatInterface';
import { PipelineStep } from './types';
import { Play, Settings, User, Bell, Terminal } from 'lucide-react';

interface LogMessage {
  timestamp: string;
  level: string;
  message: string;
}

function App() {
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [selectedStep, setSelectedStep] = useState<PipelineStep | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [repoUrl, setRepoUrl] = useState('');
  const [owner, setOwner] = useState('');
  const [repoName, setRepoName] = useState('');
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [showLogs, setShowLogs] = useState(false);

  // WebSocket connection management
  const connectWebSocket = useCallback(() => {
    const websocket = new WebSocket('ws://localhost:8000/ws');
    
    websocket.onopen = () => {
      console.log('WebSocket connected');
      setWsConnected(true);
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    websocket.onclose = () => {
      console.log('WebSocket disconnected');
      setWsConnected(false);
      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        if (!wsConnected) {
          connectWebSocket();
        }
      }, 3000);
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setWsConnected(false);
    };

    setWs(websocket);
  }, [wsConnected]);

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'step_update':
        updateStep(data.data);
        break;
      case 'log_message':
        addLogMessage(data.data);
        break;
      case 'chat_message':
        // Handle chat messages (will be handled by ChatInterface)
        break;
      case 'chat_history':
        // Handle chat history (will be handled by ChatInterface)
        break;
      case 'pong':
        // Handle ping response
        break;
      default:
        console.log('Unknown WebSocket message type:', data.type);
    }
  };

  const addLogMessage = (logData: LogMessage) => {
    setLogs(prev => [...prev, logData]);
    // Keep only last 100 logs
    if (logs.length > 100) {
      setLogs(prev => prev.slice(-100));
    }
  };

  useEffect(() => {
    // Fetch initial steps
    fetchSteps();
    
    // Setup WebSocket connection
    connectWebSocket();

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []);

  const fetchSteps = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/pipeline/steps');
      const data = await response.json();
      setSteps(data.steps);
      if (data.steps.length > 0) {
        setSelectedStep(data.steps[0]);
      }
    } catch (error) {
      console.error('Error fetching steps:', error);
    }
  };

  const updateStep = (updatedStep: PipelineStep) => {
    setSteps(prev => prev.map(step => 
      step.id === updatedStep.id ? updatedStep : step
    ));
    
    if (selectedStep && selectedStep.id === updatedStep.id) {
      setSelectedStep(updatedStep);
    }

    // Update running state based on pipeline status
    const hasRunningStep = updatedStep.status === 'running';
    const allCompleted = steps.every(step => step.status === 'completed');
    
    if (hasRunningStep) {
      setIsRunning(true);
    } else if (allCompleted) {
      setIsRunning(false);
    }
  };

  const startPipeline = async () => {
    try {
      setIsRunning(true);
      setLogs([]); // Clear previous logs
      setShowLogs(true); // Show logs when pipeline starts
      console.log('Starting pipeline with:', { owner, repoName });
      const response = await fetch('http://localhost:8000/api/pipeline/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          owner: owner,
          repo_name: repoName
        }),
      });
      console.log('Pipeline start response status:', response.status);
      const data = await response.json();
      console.log('Pipeline start response data:', data);
    } catch (error) {
      console.error('Error starting pipeline:', error);
      setIsRunning(false);
    }
  };

  // Parse owner and repo name from URL
  const handleRepoUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const url = e.target.value;
    setRepoUrl(url);
    // Try to parse GitHub repo URL
    const match = url.match(/github\.com[/:]([^/]+)\/([^/]+)(?:\.git)?/i);
    if (match) {
      setOwner(match[1]);
      setRepoName(match[2].replace(/\.git$/, ''));
      console.log('Parsed owner:', match[1], 'Parsed repo:', match[2].replace(/\.git$/, ''));
    } else {
      setOwner('');
      setRepoName('');
      console.log('Failed to parse owner/repo from URL:', url);
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'ERROR':
        return 'text-red-600';
      case 'WARNING':
        return 'text-yellow-600';
      case 'INFO':
        return 'text-blue-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Title Section */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center mb-6">
            <div className="w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Settings className="w-8 h-8 text-white animate-spin" style={{ animationDuration: '3s' }} />
            </div>
          </div>
          
          <h1 className="text-5xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-purple-900 bg-clip-text text-transparent mb-4">
            DevHex Pipeline Launcher
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Streamline your deployment process with our intelligent step-by-step pipeline system
          </p>
          
          {/* Connection Status */}
          <div className="flex justify-center mb-4">
            <div className={`flex items-center space-x-2 px-4 py-2 rounded-full text-sm font-medium ${
              wsConnected 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              <div className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-green-500' : 'bg-red-500'
              }`}></div>
              <span>{wsConnected ? 'Real-time Connected' : 'Connecting...'}</span>
            </div>
          </div>
          
          {/* Repo URL Input */}
          <div className="flex flex-col items-center mb-8">
            <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-2xl">
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                GitHub Repository URL
              </label>
              <input
                type="text"
                placeholder="https://github.com/owner/repository"
                value={repoUrl}
                onChange={handleRepoUrlChange}
                className="w-full px-6 py-4 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-4 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-200 text-lg"
              />
              
              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Owner</label>
                  <input
                    type="text"
                    value={owner}
                    readOnly
                    placeholder="Repository owner"
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg bg-gray-50 text-gray-600 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Repository</label>
                  <input
                    type="text"
                    value={repoName}
                    readOnly
                    placeholder="Repository name"
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg bg-gray-50 text-gray-600 text-sm"
                  />
                </div>
              </div>
            </div>
          </div>
          
          <div className="flex justify-center space-x-4">
            <button
              onClick={startPipeline}
              disabled={isRunning || !owner || !repoName || !wsConnected}
              className="group relative flex items-center space-x-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white px-8 py-4 rounded-2xl hover:from-green-700 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 hover:shadow-2xl disabled:hover:scale-100 disabled:hover:shadow-none"
            >
              <Play className="w-6 h-6 group-hover:animate-pulse" />
              <span className="text-lg font-semibold">
                {isRunning ? 'Pipeline Running...' : 'Launch Pipeline'}
              </span>
              {isRunning && (
                <div className="absolute -top-1 -right-1 w-3 h-3 bg-yellow-400 rounded-full animate-ping"></div>
              )}
            </button>
            
            <button
              onClick={() => setShowLogs(!showLogs)}
              className={`flex items-center space-x-2 px-4 py-4 rounded-2xl transition-all duration-300 ${
                showLogs 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              <Terminal className="w-5 h-5" />
              <span className="text-sm font-medium">Logs</span>
              {logs.length > 0 && (
                <span className="bg-red-500 text-white text-xs rounded-full px-2 py-1">
                  {logs.length}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Real-time Logs Panel */}
        {showLogs && (
          <div className="mb-8">
            <div className="bg-black rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-semibold flex items-center space-x-2">
                  <Terminal className="w-5 h-5" />
                  <span>Real-time Deployment Logs</span>
                </h3>
                <button
                  onClick={() => setLogs([])}
                  className="text-gray-400 hover:text-white text-sm"
                >
                  Clear Logs
                </button>
              </div>
              <div className="bg-gray-900 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm">
                {logs.length === 0 ? (
                  <div className="text-gray-500">No logs yet. Start a pipeline to see real-time logs.</div>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} className="mb-1">
                      <span className="text-gray-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                      <span className={`ml-2 font-semibold ${getLogLevelColor(log.level)}`}>
                        [{log.level}]
                      </span>
                      <span className="ml-2 text-gray-300">{log.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Pipeline Visual */}
        <div className="mb-12">
          <PipelineVisual 
            steps={steps} 
            onStepSelect={setSelectedStep}
            selectedStep={selectedStep}
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Output Panel */}
          <div className="lg:col-span-2">
            <OutputPanel step={selectedStep} />
          </div>

          {/* Chat Interface */}
          <div className="lg:col-span-1">
            <ChatInterface websocket={ws} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;