pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
        DEFAULT_APK_PATH = 'build/app/outputs/flutter-apk/app-release.apk'
    }
    stages {
        stage('Setup Environment') {
            steps {
                sh '''
                flutter doctor -v
                flutter pub get
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                flutter clean
                flutter build apk --release
                '''
            }
            post {
                success {
                    script {
                        // First try the default path
                        if (fileExists(env.DEFAULT_APK_PATH)) {
                            env.APK_PATH = env.DEFAULT_APK_PATH
                        } else {
                            // Fallback to searching
                            env.APK_PATH = sh(
                                script: 'find build -name "app-release.apk" | head -n 1', 
                                returnStdout: true
                            ).trim()
                        }

                        if (env.APK_PATH) {
                            echo "Found APK at: ${env.APK_PATH}"
                            archiveArtifacts artifacts: env.APK_PATH, fingerprint: true
                        } else {
                            error "APK not found. Check build logs for errors."
                        }
                    }
                }
            }
        }

        stage('Publish to Artifactory') {
            when {
                expression { env.APK_PATH != null && fileExists(env.APK_PATH) }
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    script {
                        def version = sh(
                            script: 'cat pubspec.yaml | grep version: | cut -d\' \' -f2', 
                            returnStdout: true
                        ).trim()
                        
                        def appName = sh(
                            script: 'cat pubspec.yaml | grep name: | cut -d\' \' -f2', 
                            returnStdout: true
                        ).trim()

                        sh """
                        curl -H "Authorization: Bearer $TOKEN" \
                             -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/${appName}/${version}/app-release.apk" \
                             -T ${env.APK_PATH}
                        """
                    }
                }
            }
        }
    }
    post {
        always {
            sh '''
            echo "Build artifacts:"
            ls -la build/app/outputs/flutter-apk/ || echo "No outputs directory"
            '''
            cleanWs()
        }
        failure {
            archiveArtifacts artifacts: 'build/log*', fingerprint: false
        }
    }
}