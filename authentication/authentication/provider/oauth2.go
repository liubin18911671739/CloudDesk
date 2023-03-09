package provider

import (
	"context"
	"fmt"

	"golang.org/x/oauth2"
)

type oauth2Provider struct {
	provider string
	secret   string
	cfg      *oauth2.Config
}

func (o *oauth2Provider) login(categoryID, redirect string) (string, error) {
	ss, err := signCallbackToken(o.secret, o.provider, categoryID, redirect)
	if err != nil {
		return "", err
	}

	return o.cfg.AuthCodeURL(ss), nil
}

func (o *oauth2Provider) callback(ctx context.Context, args map[string]string) (string, error) {
	tkn, err := o.cfg.Exchange(ctx, args["code"])
	if err != nil {
		return "", fmt.Errorf("exchange oauth2 token: %w", err)
	}

	return tkn.AccessToken, nil
}
