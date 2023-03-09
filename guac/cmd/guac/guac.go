package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net"
	"net/http"
	"net/url"
	"os"
	"strconv"

	"github.com/sirupsen/logrus"
	"github.com/wwt/guac"
)

var (
	guacdAddr string
	apiAddr   string
)

func init() {
	guacdAddr = os.Getenv("GUACD_ADDR")
	if guacdAddr == "" {
		guacdAddr = "isard-vpn:4822"
	}

	apiAddr = os.Getenv("GUACD_API_HOST")
	if apiAddr == "" {
		apiAddr = "isard-api:5000"
	}
}

func isAuthenticated(handler http.Handler) http.HandlerFunc {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		u := &url.URL{
			Scheme: "http",
			Host:   apiAddr,
			Path:   "/api/v3/user/owns_desktop",
		}

		body := url.Values{}
		body.Set("ip", r.URL.Query().Get("hostname"))

		req, err := http.NewRequest(http.MethodGet, u.String(), bytes.NewBufferString(body.Encode()))
		if err != nil {
			logrus.Fatal("create http request to check for authentication: %v", err)
		}

		req.Header.Add("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Add("Content-Length", strconv.Itoa(len(body.Encode())))

		session := r.URL.Query().Get("session")
		if session == "" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}

		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", session))

		rsp, err := http.DefaultClient.Do(req)
		if err != nil {
			logrus.Error("do http request to check for authentication: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		switch rsp.StatusCode {
		case http.StatusOK:
			handler.ServeHTTP(w, r)

		case http.StatusUnauthorized:
			w.WriteHeader(http.StatusUnauthorized)
			return

		default:
			b, err := io.ReadAll(rsp.Body)
			if err != nil {
				logrus.Errorf("read http response: %v", err)
				w.WriteHeader(http.StatusInternalServerError)
				return
			}
			defer rsp.Body.Close()

			w.WriteHeader(rsp.StatusCode)
			w.Write(b)
		}
	})
}

func main() {
	logrus.SetLevel(logrus.DebugLevel)

	servlet := guac.NewServer(DemoDoConnect)
	wsServer := guac.NewWebsocketServer(DemoDoConnect)

	sessions := guac.NewMemorySessionStore()
	wsServer.OnConnect = sessions.Add
	wsServer.OnDisconnect = sessions.Delete

	mux := http.NewServeMux()
	mux.HandleFunc("/tunnel", isAuthenticated(servlet))
	mux.HandleFunc("/tunnel/", isAuthenticated(servlet))
	mux.HandleFunc("/websocket-tunnel", isAuthenticated(wsServer))
	mux.HandleFunc("/sessions/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		sessions.RLock()
		defer sessions.RUnlock()

		type ConnIds struct {
			Uuid string `json:"uuid"`
			Num  int    `json:"num"`
		}

		connIds := make([]*ConnIds, len(sessions.ConnIds))

		i := 0
		for id, num := range sessions.ConnIds {
			connIds[i] = &ConnIds{
				Uuid: id,
				Num:  num,
			}
		}

		if err := json.NewEncoder(w).Encode(connIds); err != nil {
			logrus.Error(err)
		}
	})

	logrus.Println("Serving on http://127.0.0.1:4567")

	s := &http.Server{
		Addr:           "0.0.0.0:4567",
		Handler:        mux,
		ReadTimeout:    guac.SocketTimeout,
		WriteTimeout:   guac.SocketTimeout,
		MaxHeaderBytes: 1 << 20,
	}
	err := s.ListenAndServe()
	if err != nil {
		fmt.Println(err)
	}
}

// DemoDoConnect creates the tunnel to the remote machine (via guacd)
func DemoDoConnect(request *http.Request) (guac.Tunnel, error) {
	config := guac.NewGuacamoleConfiguration()

	var query url.Values
	if request.URL.RawQuery == "connect" {
		// http tunnel uses the body to pass parameters
		data, err := ioutil.ReadAll(request.Body)
		if err != nil {
			logrus.Errorf("Failed to read body ", err)
			return nil, err
		}
		_ = request.Body.Close()
		queryString := string(data)
		query, err = url.ParseQuery(queryString)
		if err != nil {
			logrus.Errorf("Failed to parse body query ", err)
			return nil, err
		}
		logrus.Debugln("body:", queryString, query)
	} else {
		query = request.URL.Query()
	}

	config.Protocol = query.Get("scheme")
	config.Parameters = map[string]string{}
	for k, v := range query {
		config.Parameters[k] = v[0]
	}

	var err error
	if query.Get("width") != "" {
		config.OptimalScreenHeight, err = strconv.Atoi(query.Get("width"))
		if err != nil || config.OptimalScreenHeight == 0 {
			logrus.Error("Invalid height")
			config.OptimalScreenHeight = 600
		}
	}
	if query.Get("height") != "" {
		config.OptimalScreenWidth, err = strconv.Atoi(query.Get("height"))
		if err != nil || config.OptimalScreenWidth == 0 {
			logrus.Error("Invalid width")
			config.OptimalScreenWidth = 800
		}
	}
	config.AudioMimetypes = []string{"audio/L16", "rate=44100", "channels=2"}

	logrus.Debug("Connecting to guacd")
	addr, err := net.ResolveTCPAddr("tcp", guacdAddr)
	if err != nil {
		logrus.Errorf("resolve guacd address: %v", err)
		return nil, err
	}

	conn, err := net.DialTCP("tcp", nil, addr)
	if err != nil {
		logrus.Errorf("error while connecting to guacd", err)
		return nil, err
	}

	stream := guac.NewStream(conn, guac.SocketTimeout)

	logrus.Debug("Connected to guacd")
	if request.URL.Query().Get("uuid") != "" {
		config.ConnectionID = request.URL.Query().Get("uuid")
	}
	logrus.Debugf("Starting handshake with %#v", config)
	err = stream.Handshake(config)
	if err != nil {
		return nil, err
	}
	logrus.Debug("Socket configured")
	return guac.NewSimpleTunnel(stream), nil
}
