package model

import (
	"context"
	"errors"
	"fmt"

	"gitlab.com/isard/isardvdi/pkg/db"

	r "gopkg.in/rethinkdb/rethinkdb-go.v6"
)

type Group struct {
	ID            string `rethinkdb:"id"`
	UID           string `rethinkdb:"uid"`
	Name          string `rethinkdb:"name"`
	Description   string `rethinkdb:"description"`
	Category      string `rethinkdb:"parent_category"`
	ExternalAppID string `rethinkdb:"external_app_id"`
	ExternalGID   string `rethinkdb:"external_gid"`
}

func (g *Group) GenerateNameExternal(prv string) {
	g.Name = fmt.Sprintf("%s_%s_%s", prv, g.ExternalAppID, g.ExternalGID)
}

func (g *Group) LoadExternal(ctx context.Context, sess r.QueryExecutor) error {
	res, err := r.Table("groups").Filter(r.And(
		r.Eq(r.Row.Field("external_app_id"), g.ExternalAppID),
		r.Eq(r.Row.Field("external_gid"), g.ExternalGID),
	), r.FilterOpts{}).Run(sess)
	if err != nil {
		return err
	}
	defer res.Close()

	if err := res.One(g); err != nil {
		if errors.Is(err, r.ErrEmptyResult) {
			return db.ErrNotFound
		}

		return fmt.Errorf("read db response: %w", err)
	}

	return nil
}

func (g *Group) Exists(ctx context.Context, sess r.QueryExecutor) (bool, error) {
	// Check if the group is original of IsardVDI or is a group mapped from elsewhere
	if g.ExternalAppID != "" && g.ExternalGID != "" {
		res, err := r.Table("groups").Filter(r.And(
			r.Eq(r.Row.Field("external_app_id"), g.ExternalAppID),
			r.Eq(r.Row.Field("external_gid"), g.ExternalGID),
		), r.FilterOpts{}).Run(sess)
		if err != nil {
			return false, err
		}
		defer res.Close()

		if res.IsNil() {
			return false, nil
		}

		if err := res.One(g); err != nil {
			if errors.Is(err, r.ErrEmptyResult) {
				return false, nil
			}

			return false, fmt.Errorf("read db response: %w", err)
		}

		return true, nil

	} else {
		res, err := r.Table("groups").Get(g.ID).Run(sess)
		if err != nil {
			return false, err
		}
		defer res.Close()

		if res.IsNil() {
			return false, nil
		}

		if err := res.One(g); err != nil {
			if errors.Is(err, r.ErrEmptyResult) {
				return false, nil
			}

			return false, fmt.Errorf("read db response: %w", err)
		}

		return true, nil
	}
}
