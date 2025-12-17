'use client'

import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'

export default function HomePage() {
  const router = useRouter()

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="max-w-2xl w-full"
      >
        <div className="bg-bg-card border border-gray-800 rounded-3xl p-12 text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-accent to-accent-hover rounded-2xl mb-6">
            <span className="text-4xl font-serif text-bg-base">D</span>
          </div>
          
          <h1 className="text-5xl font-serif mb-4 tracking-tight">
            DepoDigest
          </h1>
          
          <p className="text-gray-400 text-lg mb-12">
            AI-powered deposition summarization
            <br />
            <span className="text-sm">6.4x faster than traditional methods</span>
          </p>
          
          <button
            onClick={() => router.push('/upload')}
            className="px-8 py-4 bg-accent hover:bg-accent-hover text-bg-base font-semibold rounded-xl transition-all transform hover:scale-105 hover:shadow-lg"
          >
            Start Processing
          </button>
          
          <div className="mt-12 pt-8 border-t border-gray-800 text-sm text-gray-500">
            <div className="grid grid-cols-3 gap-8 max-w-lg mx-auto">
              <div>
                <div className="text-2xl font-bold text-accent mb-1">3s</div>
                <div>PDF Extract</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-accent mb-1">30s</div>
                <div>AI Summary</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-accent mb-1">90%</div>
                <div>Cache Hit</div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

