pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
    }
    stages {
        stage('Build') {
            steps {
                sh '''
                # Clean previous builds
                flutter clean
                
                # Build with detailed logging
                flutter build apk --release --no-pub -v 2>&1 | tee build.log
                
                # Find the APK wherever it was generated
                find build -name "*.apk" | head -n 1 > apk_path.txt
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build.log', fingerprint: false
                }
                success {
                    script {
                        // Read the found APK path
                        env.APK_PATH = readFile('apk_path.txt').trim()
                        
                        if (env.APK_PATH) {
                            echo "Found APK at: ${env.APK_PATH}"
                            archiveArtifacts artifacts: env.APK_PATH, fingerprint: true
                        } else {
                            error """No APK file was generated. Possible causes:
                            - Build failed (check build.log)
                            - Unexpected output path
                            - Permission issues
                            """
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            sh '''
            echo "Full build directory structure:"
            find build -type f || echo "No build files found"
            
            echo "Build log excerpts:"
            grep -i error build.log || echo "No errors found in build log"
            '''
        }
    }
}