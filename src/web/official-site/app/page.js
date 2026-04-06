'use client'

import { Shield, Code, Zap, CheckCircle, ArrowRight, Menu, X } from 'lucide-react'
import { useState } from 'react'

export default function Home() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const features = [
    {
      icon: <Zap className="w-8 h-8 text-blue-400" />,
      title: "Multi-Engine Detection",
      description: "Combines 5 independent detection engines with Bayesian fusion for unmatched accuracy."
    },
    {
      icon: <Shield className="w-8 h-8 text-green-400" />,
      title: "Enterprise Grade Security",
      description: "All processing happens locally. Your code never leaves your infrastructure."
    },
    {
      icon: <Code className="w-8 h-8 text-purple-400" />,
      title: "50+ Language Support",
      description: "Detect similarities across every major programming language and framework."
    },
    {
      icon: <CheckCircle className="w-8 h-8 text-amber-400" />,
      title: "99.8% Accuracy",
      description: "Industry leading false positive rate of less than 0.2% on real world codebases."
    }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-slate-950/80 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <Shield className="w-8 h-8 text-blue-500" />
              <span className="text-xl font-bold">IntegrityDesk</span>
            </div>
            
            <div className="hidden md:flex items-center space-x-8">
              <a href="#features" className="text-slate-300 hover:text-white transition-colors">Features</a>
              <a href="#how-it-works" className="text-slate-300 hover:text-white transition-colors">How It Works</a>
              <a href="#pricing" className="text-slate-300 hover:text-white transition-colors">Pricing</a>
              <a href="#contact" className="text-slate-300 hover:text-white transition-colors">Contact</a>
              <a href="http://localhost:3003" className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-medium transition-colors">
                Dashboard
              </a>
            </div>

            <button 
              className="md:hidden text-slate-300"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden bg-slate-900 border-t border-slate-800 px-4 py-4 space-y-4">
            <a href="#features" className="block text-slate-300 hover:text-white">Features</a>
            <a href="#how-it-works" className="block text-slate-300 hover:text-white">How It Works</a>
            <a href="#pricing" className="block text-slate-300 hover:text-white">Pricing</a>
            <a href="#contact" className="block text-slate-300 hover:text-white">Contact</a>
            <a href="http://localhost:3003" className="block bg-blue-600 text-center py-2 rounded-lg font-medium">
              Dashboard
            </a>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-block mb-6 px-4 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium">
            Code Similarity Detection Platform
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            Protect Your Codebase
          </h1>
          
          <p className="text-xl md:text-2xl text-slate-400 max-w-3xl mx-auto mb-10">
            Enterprise-grade multi-engine code similarity detection system. Stop plagiarism, enforce code standards, and protect your intellectual property.
          </p>
          
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <a href="http://localhost:3003" className="bg-blue-600 hover:bg-blue-700 px-8 py-4 rounded-xl font-semibold text-lg flex items-center justify-center gap-2 transition-all hover:scale-105">
              Get Started <ArrowRight className="w-5 h-5" />
            </a>
            <button className="bg-slate-800 hover:bg-slate-700 px-8 py-4 rounded-xl font-semibold text-lg transition-colors">
              View Documentation
            </button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-4">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Why IntegrityDesk?</h2>
          <p className="text-slate-400 text-center max-w-2xl mx-auto mb-16">
            Built from the ground up for modern development teams with enterprise requirements.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <div 
                key={index} 
                className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 hover:border-blue-500/50 transition-all hover:-translate-y-1"
              >
                <div className="mb-4">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                <p className="text-slate-400">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto bg-gradient-to-r from-blue-600 to-indigo-600 rounded-3xl p-12 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Ready to get started?</h2>
          <p className="text-blue-100 text-lg mb-8 max-w-2xl mx-auto">
            Start scanning your codebase today. No credit card required.
          </p>
          <a href="http://localhost:3003" className="inline-block bg-white text-slate-900 px-8 py-4 rounded-xl font-semibold text-lg hover:bg-slate-100 transition-colors">
            Launch Dashboard
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 border-t border-slate-800">
        <div className="max-w-7xl mx-auto text-center text-slate-500">
          <p>© 2026 IntegrityDesk. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
