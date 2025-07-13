pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://trialjq29zm.jfrog.io/artifactory/api/pub/dart-pub-pub/'
    }
    stages {
        stage('Setup') {
            steps {
                withCredentials([string(
                    credentialsId: 'artifactory-token', // Store token in Jenkins credentials
                    variable: 'DART_PUB_TOKEN'
                )]) {
                    sh '''
                    # Non-interactive token setup
                    mkdir -p ~/.config/dart
                    echo '{
                      "accessToken":"$DART_PUB_TOKEN",
                      "refreshToken":"$DART_PUB_TOKEN",
                      "tokenEndpoint":"$PUB_HOSTED_URL",
                      "scopes":["$PUB_HOSTED_URL"],
                      "expiration":9999999999999
                    }' > ~/.config/dart/pub-credentials.json
                    
                    flutter doctor -v
                    '''
                }
            }
        }
        stage('Build') {
            steps {
                sh '''
                flutter pub get
                flutter build apk --release
                '''
            }
        }
    }
}