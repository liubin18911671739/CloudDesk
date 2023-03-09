package authentication

import (
	"context"

	"github.com/crewjam/saml/samlsp"
	"github.com/stretchr/testify/mock"
	"gitlab.com/isard/isardvdi/authentication/authentication/provider"
)

type AuthenticationMock struct {
	mock.Mock
}

func (m *AuthenticationMock) Login(ctx context.Context, provider string, categoryID string, args map[string]string) (string, string, error) {
	mArgs := m.Called(ctx, provider, categoryID, args)
	return mArgs.String(0), mArgs.String(1), mArgs.Error(2)
}

func (m *AuthenticationMock) Callback(ctx context.Context, args map[string]string) (string, string, error) {
	mArgs := m.Called(ctx, args)
	return mArgs.String(0), mArgs.String(1), mArgs.Error(2)
}

func (m *AuthenticationMock) Check(ctx context.Context, tkn string) error {
	mArgs := m.Called(ctx, tkn)
	return mArgs.Error(0)
}

func (m *AuthenticationMock) Providers() []string {
	return []string{"local", "google", "ldap", "saml"}
}

func (m *AuthenticationMock) Provider(prv string) provider.Provider {
	mArgs := m.Called(prv)
	return mArgs.Get(0).(provider.Provider)
}

func (m *AuthenticationMock) SAML() *samlsp.Middleware {
	mArgs := m.Called()
	return mArgs.Get(0).(*samlsp.Middleware)
}
