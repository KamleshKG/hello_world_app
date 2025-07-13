pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://trialjq29zm.jfrog.io/artifactory/api/pub/dart-pub-pub/'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory/flutter-app-releases/'
    }
    stages {
        stage('Build') {
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Configure Dart auth
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
                    flutter build apk --release --no-pub
                    '''
                }
            }
        }
        stage('Publish Artifacts') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'jfrog-creds',
                    usernameVariable: 'JFROG_USER',
                    passwordVariable: 'JFROG_PASS'
                )]) {
                    sh '''
                    # Upload APK with metadata
                    curl -u$JFROG_USER:$JFROG_PASS \
                         -H "X-Checksum-Sha1: $(sha1sum build/app/outputs/flutter-apk/app-release.apk | cut -d' ' -f1)" \
                         -T build/app/outputs/flutter-apk/app-release.apk \
                         "${ARTIFACTORY_URL}${BUILD_NUMBER}/app-release.apk"
                    '''
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/*.apk', fingerprint: true
        }
        success {
            slackSend channel: '#builds',
                      message: "SUCCESS: Flutter build ${BUILD_NUMBER} - ${BUILD_URL}"
        }
        failure {
            slackSend channel: '#builds',
                      message: "FAILED: Flutter build ${BUILD_NUMBER} - ${BUILD_URL}"
        }
    }
}