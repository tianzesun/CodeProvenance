'use client'

import { Shield, Code, Zap, CheckCircle, ArrowRight, Menu, X, Sun, Moon } from 'lucide-react'
import { useState, useEffect } from 'react'

export default function Home() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [darkMode, setDarkMode] = useState(true)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const savedTheme = localStorage.getItem('theme')
    if (savedTheme) {
      setDarkMode(savedTheme === 'dark')
    }
  }, [])

  useEffect(() => {
    if (mounted) {
      localStorage.setItem('theme', darkMode ? 'dark' : 'light')
      document.documentElement.classList.toggle('dark', darkMode)
    }
  }, [darkMode, mounted])

  const toggleTheme = () => {
    setDarkMode(!darkMode)
  }

  const features = [
    {
      icon: <Zap className={`w-8 h-8 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`} />,
      title: "Multi-Engine Detection",
      description: "Combines 5 independent detection engines with Bayesian fusion for unmatched accuracy."
    },
    {
      icon: <Shield className={`w-8 h-8 ${darkMode ? 'text-green-400' : 'text-green-600'}`} />,
      title: "Enterprise Grade Security",
      description: "All processing happens locally. Your code never leaves your infrastructure."
    },
    {
      icon: <Code className={`w-8 h-8 ${darkMode ? 'text-purple-400' : 'text-purple-600'}`} />,
      title: "50+ Language Support",
      description: "Detect similarities across every major programming language and framework."
    },
    {
      icon: <CheckCircle className={`w-8 h-8 ${darkMode ? 'text-amber-400' : 'text-amber-600'}`} />,
      title: "99.8% Accuracy",
      description: "Industry leading false positive rate of less than 0.2% on real world codebases."
    }
  ]

  const bgClass = darkMode 
    ? 'bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950' 
    : 'bg-gradient-to-b from-slate-50 via-white to-slate-100'
  
  const textPrimary = darkMode ? 'text-white' : 'text-slate-900'
  const textSecondary = darkMode ? 'text-slate-400' : 'text-slate-600'
  const textMuted = darkMode ? 'text-slate-500' : 'text-slate-500'
  const cardBg = darkMode ? 'bg-slate-800/50' : 'bg-white/70'
  const cardBorder = darkMode ? 'border-slate-700' : 'border-slate-200'
  const navBg = darkMode ? 'bg-slate-950/80' : 'bg-white/80'
  const navBorder = darkMode ? 'border-slate-800' : 'border-slate-200'
  const navText = darkMode ? 'text-slate-300' : 'text-slate-600'
  const navTextHover = darkMode ? 'hover:text-white' : 'hover:text-slate-900'

  return (
    <div className={`min-h-screen ${bgClass} transition-colors duration-300`}>
      {/* Navigation */}
      <nav className={`fixed top-0 w-full z-50 ${navBg} backdrop-blur-md border-b ${navBorder}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <Shield className={`w-8 h-8 ${darkMode ? 'text-blue-500' : 'text-blue-600'}`} />
              <span className={`text-xl font-bold ${textPrimary}`}>IntegrityDesk</span>
            </div>
            
            <div className="hidden md:flex items-center space-x-8">
              <a href="#features" className={`${navText} ${navTextHover} transition-colors`}>Features</a>
              <a href="#how-it-works" className={`${navText} ${navTextHover} transition-colors`}>How It Works</a>
              <a href="#pricing" className={`${navText} ${navTextHover} transition-colors`}>Pricing</a>
              <a href="#contact" className={`${navText} ${navTextHover} transition-colors`}>Contact</a>
              
              {/* Theme Toggle */}
              <button
                onClick={toggleTheme}
                className={`p-2 rounded-lg ${darkMode ? 'bg-slate-800 text-yellow-400 hover:bg-slate-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'} transition-colors`}
                aria-label="Toggle theme"
              >
                {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
              
              <a href="http://localhost:3003" className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-medium transition-colors text-white">
                Dashboard
              </a>
            </div>

            <div className="flex items-center space-x-4 md:hidden">
              {/* Mobile Theme Toggle */}
              <button
                onClick={toggleTheme}
                className={`p-2 rounded-lg ${darkMode ? 'bg-slate-800 text-yellow-400' : 'bg-slate-100 text-slate-600'}`}
                aria-label="Toggle theme"
              >
                {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
              
              <button 
                className={`${navText} md:hidden`}
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className={`md:hidden ${darkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'} border-t px-4 py-4 space-y-4`}>
            <a href="#features" className={`block ${navText}`}>Features</a>
            <a href="#how-it-works" className={`block ${navText}`}>How It Works</a>
            <a href="#pricing" className={`block ${navText}`}>Pricing</a>
            <a href="#contact" className={`block ${navText}`}>Contact</a>
            <a href="http://localhost:3003" className="block bg-blue-600 text-white text-center py-2 rounded-lg font-medium">
              Dashboard
            </a>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <div className={`inline-block mb-6 px-4 py-1 rounded-full ${darkMode ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' : 'bg-blue-100 border-blue-200 text-blue-600'} border text-sm font-medium`}>
            Code Similarity Detection Platform
          </div>
          
          <h1 className={`text-5xl md:text-7xl font-bold mb-6 ${darkMode ? 'bg-gradient-to-r from-white via-slate-200 to-slate-400' : 'bg-gradient-to-r from-slate-900 via-slate-700 to-slate-500'} bg-clip-text text-transparent`}>
            Protect Your Codebase
          </h1>
          
          <p className={`text-xl md:text-2xl ${textSecondary} max-w-3xl mx-auto mb-10`}>
            Enterprise-grade multi-engine code similarity detection system. Stop plagiarism, enforce code standards, and protect your intellectual property.
          </p>
          
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <a href="http://localhost:3003" className="bg-blue-600 hover:bg-blue-700 px-8 py-4 rounded-xl font-semibold text-lg flex items-center justify-center gap-2 transition-all hover:scale-105 text-white">
              Get Started <ArrowRight className="w-5 h-5" />
            </a>
            <button className={`${darkMode ? 'bg-slate-800 hover:bg-slate-700 text-white' : 'bg-slate-200 hover:bg-slate-300 text-slate-900'} px-8 py-4 rounded-xl font-semibold text-lg transition-colors`}>
              View Documentation
            </button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-4">
        <div className="max-w-7xl mx-auto">
          <h2 className={`text-3xl md:text-4xl font-bold text-center mb-4 ${textPrimary}`}>Why IntegrityDesk?</h2>
          <p className={`${textSecondary} text-center max-w-2xl mx-auto mb-16`}>
            Built from the ground up for modern development teams with enterprise requirements.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <div 
                key={index} 
                className={`${cardBg} backdrop-blur-sm border ${cardBorder} rounded-2xl p-6 hover:border-blue-500/50 transition-all hover:-translate-y-1`}
              >
                <div className="mb-4">
                  {feature.icon}
                </div>
                <h3 className={`text-xl font-semibold mb-2 ${textPrimary}`}>{feature.title}</h3>
                <p className={textSecondary}>{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto bg-gradient-to-r from-blue-600 to-indigo-600 rounded-3xl p-12 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">Ready to get started?</h2>
          <p className="text-blue-100 text-lg mb-8 max-w-2xl mx-auto">
            Start scanning your codebase today. No credit card required.
          </p>
          <a href="http://localhost:3003" className="inline-block bg-white text-slate-900 px-8 py-4 rounded-xl font-semibold text-lg hover:bg-slate-100 transition-colors">
            Launch Dashboard
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className={`py-12 px-4 border-t ${darkMode ? 'border-slate-800' : 'border-slate-200'}`}>
        <div className="max-w-7xl mx-auto text-center">
          <p className={textMuted}>© 2026 IntegrityDesk. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}