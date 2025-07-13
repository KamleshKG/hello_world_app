pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://pub.dartlang.org'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
        BUILD_DIR = 'build/app/outputs/flutter-apk'  // Define build directory
    }
    stages {
        stage('Setup Flutter') {
            steps {
                sh '''
                flutter doctor -v --suppress-analytics
                '''
            }
        }
        
        stage('Build') {
            environment {
                PUB_HOSTED_URL = "${ARTIFACTORY_URL}/api/pub/dart-pub-pub/"
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    mkdir -p ~/.config/dart
                    cat > ~/.config/dart/pub-credentials.json <<EOF
                    {
                      "accessToken":"$TOKEN",
                      "refreshToken":"$TOKEN",
                      "tokenEndpoint":"$PUB_HOSTED_URL",
                      "scopes":["$PUB_HOSTED_URL"],
                      "expiration":9999999999999
                    }
                    EOF
                    
                    flutter pub get
                    flutter clean  # Ensure clean build
                    flutter build apk --release --no-pub
                    '''
                }
            }
            post {
                success {
                    script {
                        // Verify the APK exists before archiving
                        if (fileExists("${env.BUILD_DIR}/app-release.apk")) {
                            archiveArtifacts artifacts: "${env.BUILD_DIR}/app-release.apk", fingerprint: true
                        } else {
                            error "APK file not found at ${env.BUILD_DIR}/app-release.apk"
                        }
                    }
                    stash includes: 'build/web/**', name: 'web-build'
                    stash includes: 'build/ios/**', name: 'ios-build'
                }
            }
        }
        
        stage('Publish APK') {
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    script {
                        if (fileExists("${env.BUILD_DIR}/app-release.apk")) {
                            sh """
                            curl -H "Authorization: Bearer $TOKEN" \
                                 -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/app-release.apk" \
                                 -T ${env.BUILD_DIR}/app-release.apk
                            """
                        } else {
                            error "APK file not found for publishing"
                        }
                    }
                }
            }
        }
        
        stage('Publish Web Assets') {
            steps {
                unstash 'web-build'
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Package and publish web assets
                    cd build/web
                    zip -r web-assets.zip .
                    curl -H "Authorization: Bearer $TOKEN" \
                         -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/web-assets.zip" \
                         -T web-assets.zip
                    '''
                }
            }
        }
        
        stage('Publish iOS Archive') {
            steps {
                unstash 'ios-build'
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Package and publish iOS archive
                    cd build/ios
                    zip -r ios-archive.zip .
                    curl -H "Authorization: Bearer $TOKEN" \
                         -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/ios-archive.zip" \
                         -T ios-archive.zip
                    '''
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
            sh 'flutter clean'  # Clean up build artifacts
        }
    }
}