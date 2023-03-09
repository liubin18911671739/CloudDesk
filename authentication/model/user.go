package model

import (
	"context"
	"errors"
	"fmt"

	"gitlab.com/isard/isardvdi/pkg/db"

	r "gopkg.in/rethinkdb/rethinkdb-go.v6"
)

// User is an user of CECD
type User struct {
	ID       string `rethinkdb:"id"`
	UID      string `rethinkdb:"uid"`
	Username string `rethinkdb:"username"`
	Password string `rethinkdb:"password"`
	Provider string `rethinkdb:"provider"`
	Active   bool   `rethinkdb:"active"`

	Category string `rethinkdb:"category"`
	Role     Role   `rethinkdb:"role"`
	Group    string `rethinkdb:"group"`

	Name  string `rethinkdb:"name"`
	Email string `rethinkdb:"email"`
	Photo string `rethinkdb:"photo"`

	Accessed float64 `rethinkdb:"accessed"`
}

func (u *User) Load(ctx context.Context, sess r.QueryExecutor) error {
	res, err := r.Table("users").Get(u.ID).Run(sess)
	if err != nil {
		return err
	}
	defer res.Close()

	if err := res.One(u); err != nil {
		if errors.Is(err, r.ErrEmptyResult) {
			return db.ErrNotFound
		}

		return fmt.Errorf("read db response: %w", err)
	}

	return nil
}

func (u *User) LoadWithoutID(ctx context.Context, sess r.QueryExecutor) error {
	res, err := r.Table("users").Filter(r.And(
		r.Eq(r.Row.Field("uid"), u.UID),
		r.Eq(r.Row.Field("provider"), u.Provider),
		r.Eq(r.Row.Field("category"), u.Category),
	), r.FilterOpts{}).Run(sess)
	if err != nil {
		return err
	}
	defer res.Close()

	if err := res.One(u); err != nil {
		if errors.Is(err, r.ErrEmptyResult) {
			return db.ErrNotFound
		}

		return fmt.Errorf("read db response: %w", err)
	}

	return nil
}

func (u *User) Update(ctx context.Context, sess r.QueryExecutor) error {
	_, err := r.Table("users").Get(u.ID).Update(u).Run(sess)
	return err
}

func (u *User) Exists(ctx context.Context, sess r.QueryExecutor) (bool, error) {
	res, err := r.Table("users").Filter(r.And(
		r.Eq(r.Row.Field("uid"), u.UID),
		r.Eq(r.Row.Field("provider"), u.Provider),
		r.Eq(r.Row.Field("category"), u.Category),
	), r.FilterOpts{}).Run(sess)
	if err != nil {
		return false, err
	}
	defer res.Close()

	if res.IsNil() {
		return false, nil
	}

	if err := res.One(u); err != nil {
		if errors.Is(err, r.ErrEmptyResult) {
			return false, nil
		}

		return false, fmt.Errorf("read db response: %w", err)
	}

	return true, nil
}

func (u *User) LoadWithoutOverride(u2 *User) {
	if u.Category == "" {
		u.Category = u2.Category
	}

	if u.Role == "" {
		u.Role = u2.Role
	}

	if u.Group == "" {
		u.Group = u2.Group
	}

	if u.Name == "" {
		u.Name = u2.Name
	}

	if u.Email == "" {
		u.Email = u2.Email
	}

	if u.Photo == "" {
		u.Photo = u2.Photo
	}

	if u.Accessed == 0 {
		u.Accessed = u2.Accessed
	}
}
