import chokidar from 'chokidar'
import { spawn } from 'node:child_process'
import { modulesDir } from './module-utils.mjs'

let running = false
let pending = false

function runGenerate() {
  if (running) {
    pending = true
    return
  }

  running = true
  const child = spawn(process.execPath, ['scripts/generate-lowdefy.mjs'], {
    cwd: new URL('..', import.meta.url).pathname,
    stdio: 'inherit',
  })

  child.on('exit', (code) => {
    running = false
    if (code !== 0) {
      console.error(`Module registry generation failed with exit code ${code}.`)
    }
    if (pending) {
      pending = false
      runGenerate()
    }
  })
}

console.log(`Watching launcher modules in ${modulesDir}`)
runGenerate()

chokidar
  .watch([`${modulesDir}/**/*.json`], {
    ignoreInitial: true,
  })
  .on('add', runGenerate)
  .on('change', runGenerate)
  .on('unlink', runGenerate)
